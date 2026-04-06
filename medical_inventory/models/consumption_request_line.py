from odoo import models, fields, api


class ConsumptionRequestLine(models.Model):
    _name = 'medical.consumption.request.line'
    _description = 'Medical Consumption Request Line'

    request_id = fields.Many2one(
        'medical.consumption.request', string='Request',
        required=True, ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain=[('type', 'in', ['product', 'consu'])]
    )
    product_uom_id = fields.Many2one(
        'uom.uom', string='Unit of Measure'
    )
    quantity = fields.Float(string='Quantity Requested', default=1.0, required=True)
    lot_id = fields.Many2one(
        'stock.lot', string='Batch / Lot',
        domain="[('product_id', '=', product_id)]",
        help='Select a specific batch to track expiry dates'
    )
    expiry_date = fields.Date(
        string='Expiry Date', related='lot_id.expiration_date',
        store=True, readonly=True
    )
    available_qty = fields.Float(
        string='Available in Store', compute='_compute_available_qty'
    )
    notes = fields.Char(string='Note')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id

    @api.depends('product_id', 'request_id.source_location_id')
    def _compute_available_qty(self):
        for line in self:
            if line.product_id and line.request_id.source_location_id:
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', line.request_id.source_location_id.id),
                ], limit=1)
                line.available_qty = quant.quantity if quant else 0.0
            else:
                line.available_qty = 0.0
