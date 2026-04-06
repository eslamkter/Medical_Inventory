from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MedicalStockReceive(models.Model):
    _name = 'medical.stock.receive'
    _description = 'Medical Inventory - Receive Stock'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_receive desc'

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New')
    )
    date_receive = fields.Datetime(
        string='Receive Date', default=fields.Datetime.now,
        required=True, tracking=True
    )
    received_by = fields.Many2one(
        'res.users', string='Received By',
        default=lambda self: self.env.user, required=True
    )
    destination_location_id = fields.Many2one(
        'stock.location', string='Store Into',
        required=True, tracking=True,
        domain=[('usage', '=', 'internal')],
    )
    supplier = fields.Char(string='Supplier / Source')
    notes = fields.Text(string='Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many(
        'medical.stock.receive.line', 'receive_id',
        string='Items to Receive'
    )
    stock_picking_id = fields.Many2one(
        'stock.picking', string='Stock Entry', readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'medical.stock.receive') or _('New')
        return super().create(vals_list)

    def action_receive(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Please add at least one item before receiving.'))

        # Directly update stock using inventory adjustments (stock.quant)
        # This is the most reliable way in Odoo 19 - no picking wizard issues
        for line in self.line_ids:
            quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', self.destination_location_id.id),
                ('lot_id', '=', line.lot_id.id if line.lot_id else False),
            ], limit=1)

            if quant:
                quant.sudo().write({
                    'quantity': quant.quantity + line.quantity,
                })
            else:
                self.env['stock.quant'].sudo().create({
                    'product_id': line.product_id.id,
                    'location_id': self.destination_location_id.id,
                    'quantity': line.quantity,
                    'lot_id': line.lot_id.id if line.lot_id else False,
                })

        self.state = 'done'
        self.message_post(body=_('Stock received and inventory updated successfully.'))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'medical.stock.receive',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('Cannot cancel a completed receipt.'))
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'


class MedicalStockReceiveLine(models.Model):
    _name = 'medical.stock.receive.line'
    _description = 'Medical Stock Receive Line'

    receive_id = fields.Many2one(
        'medical.stock.receive', string='Receipt',
        required=True, ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain=[('type', 'in', ['product', 'consu'])]
    )
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    lot_id = fields.Many2one(
        'stock.lot', string='Batch / Lot',
        domain="[('product_id', '=', product_id)]"
    )
    expiry_date = fields.Datetime(string='Expiry Date')
    notes = fields.Char(string='Note')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id:
            lot = self.lot_id
            if hasattr(lot, 'expiration_date') and lot.expiration_date:
                self.expiry_date = lot.expiration_date
