from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConsumptionRequest(models.Model):
    _name = 'medical.consumption.request'
    _description = 'Medical Inventory Consumption Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_request desc'

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New')
    )
    date_request = fields.Datetime(
        string='Request Date', default=fields.Datetime.now,
        required=True, tracking=True
    )
    requested_by = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user, required=True, tracking=True
    )
    department_location_id = fields.Many2one(
        'stock.location', string='Clinic / Department',
        required=True, tracking=True,
        domain=[('usage', '=', 'internal')],
        help='The clinic or department requesting the items'
    )
    source_location_id = fields.Many2one(
        'stock.location', string='Take From (Warehouse/Store)',
        required=True, tracking=True,
        domain=[('usage', '=', 'internal')],
        help='The main warehouse or store to take items from'
    )
    notes = fields.Text(string='Notes / Reason')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)

    line_ids = fields.One2many(
        'medical.consumption.request.line', 'request_id',
        string='Items Requested'
    )
    stock_picking_id = fields.Many2one(
        'stock.picking', string='Stock Transfer', readonly=True
    )
    approved_by = fields.Many2one(
        'res.users', string='Approved By', readonly=True, tracking=True
    )
    date_approved = fields.Datetime(string='Approval Date', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'medical.consumption.request') or _('New')
        return super().create(vals_list)

    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Please add at least one item before submitting.'))
            rec.state = 'submitted'

    def action_approve(self):
        for rec in self:
            rec.state = 'approved'
            rec.approved_by = self.env.user
            rec.date_approved = fields.Datetime.now()

    def action_reject(self):
        for rec in self:
            rec.state = 'rejected'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('Cannot cancel a completed request.'))
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_process_stock(self):
        """Create internal stock transfer to move items out."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Request must be approved before processing stock.'))

        # Find internal operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
        ], limit=1)
        if not picking_type:
            raise UserError(_('No internal transfer operation type found. Please configure your warehouse.'))

        # Build move lines - no 'name' field in Odoo 19 stock.move
        move_vals = []
        for line in self.line_ids:
            move_vals.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom': line.product_uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.department_location_id.id,
            }))

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.source_location_id.id,
            'location_dest_id': self.department_location_id.id,
            'origin': self.name,
            'move_ids': move_vals,
        })
        picking.action_confirm()
        picking.action_assign()

        self.stock_picking_id = picking.id
        self.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }
