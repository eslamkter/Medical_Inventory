from odoo import models, fields, api, _


class MedicalStockAlert(models.Model):
    _name = 'medical.stock.alert'
    _description = 'Medical Low Stock Alert Rule'
    _inherit = ['mail.thread']

    product_id = fields.Many2one(
        'product.product', string='Product', required=True
    )
    location_id = fields.Many2one(
        'stock.location', string='Clinic / Location', required=True,
        domain=[('usage', '=', 'internal')]
    )
    minimum_qty = fields.Float(string='Minimum Quantity', required=True, default=5.0)
    current_qty = fields.Float(
        string='Current Quantity', compute='_compute_current_qty', store=False
    )
    is_below_minimum = fields.Boolean(
        string='Below Minimum?', compute='_compute_current_qty', store=False
    )
    active = fields.Boolean(default=True)

    @api.depends('product_id', 'location_id', 'minimum_qty')
    def _compute_current_qty(self):
        for alert in self:
            if alert.product_id and alert.location_id:
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', alert.product_id.id),
                    ('location_id', '=', alert.location_id.id),
                ], limit=1)
                alert.current_qty = quant.quantity if quant else 0.0
                alert.is_below_minimum = alert.current_qty < alert.minimum_qty
            else:
                alert.current_qty = 0.0
                alert.is_below_minimum = False

    def action_check_all_alerts(self):
        """Called by scheduled action to log warnings on items below minimum."""
        alerts = self.search([('active', '=', True)])
        for alert in alerts:
            alert._compute_current_qty()
            if alert.is_below_minimum:
                alert.message_post(
                    body=_(
                        'LOW STOCK ALERT: %s at %s is below minimum. '
                        'Current: %.2f | Minimum: %.2f'
                    ) % (
                        alert.product_id.display_name,
                        alert.location_id.complete_name,
                        alert.current_qty,
                        alert.minimum_qty,
                    ),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )


class StockLotExpiry(models.Model):
    """Extend stock.lot to surface expiry information more clearly."""
    _inherit = 'stock.lot'

    days_to_expiry = fields.Integer(
        string='Days to Expiry', compute='_compute_days_to_expiry', store=False
    )
    expiry_status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Expiring Soon (30 days)'),
        ('critical', 'Expiring Soon (7 days)'),
        ('expired', 'Expired'),
        ('no_date', 'No Expiry Set'),
    ], string='Expiry Status', compute='_compute_days_to_expiry', store=False)

    @api.depends('expiration_date')
    def _compute_days_to_expiry(self):
        today = fields.Date.today()
        for lot in self:
            if not lot.expiration_date:
                lot.days_to_expiry = 0
                lot.expiry_status = 'no_date'
            else:
                delta = (lot.expiration_date - today).days
                lot.days_to_expiry = delta
                if delta < 0:
                    lot.expiry_status = 'expired'
                elif delta <= 7:
                    lot.expiry_status = 'critical'
                elif delta <= 30:
                    lot.expiry_status = 'warning'
                else:
                    lot.expiry_status = 'ok'
