from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MedicalStockReceive(models.Model):
    _name = 'medical.stock.receive'
    _description = 'Medical Stock Receive'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_receive desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('medical.stock.receive'))
    date_receive = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    received_by = fields.Many2one('res.users', string='Received By', default=lambda self: self.env.user)
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    vendor_name = fields.Char(string='Vendor Name (if not in system)')
    vendor_invoice_ref = fields.Char(string='Invoice / Delivery Note Ref')
    destination_location_id = fields.Many2one('stock.location', string='Store Into', required=True,
                                              domain=[('usage', '=', 'internal')])
    notes = fields.Text(string='Notes')
    line_ids = fields.One2many('medical.stock.receive.line', 'receive_id', string='Items Received')
    total_value = fields.Float(string='Total Value', compute='_compute_total_value', store=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('done', 'Received'), ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    @api.depends('line_ids.subtotal')
    def _compute_total_value(self):
        for record in self:
            record.total_value = sum(line.subtotal for line in record.line_ids)

    # حقول حساب المورد
    amount_paid = fields.Float(string='المبلغ المدفوع', default=0.0)
    vendor_old_balance = fields.Float(string='الرصيد القديم للمورد',
                                       compute='_compute_vendor_balances')
    vendor_new_balance = fields.Float(string='الرصيد الجديد للمورد',
                                       compute='_compute_vendor_balances')

    @api.depends('vendor_id', 'total_value', 'amount_paid')
    def _compute_vendor_balances(self):
        for rec in self:
            if rec.vendor_id:
                account = self.env['medical.vendor.account'].search(
                    [('vendor_id', '=', rec.vendor_id.id)], limit=1)
                old_balance = account.balance_due if account else 0.0
                # If already done, old balance was before this receive
                if rec.state == 'done':
                    old_balance = old_balance - rec.total_value + rec.amount_paid
                rec.vendor_old_balance = old_balance
                rec.vendor_new_balance = old_balance + rec.total_value - rec.amount_paid
            else:
                rec.vendor_old_balance = 0.0
                rec.vendor_new_balance = 0.0

    amount_due = fields.Float(string='المبلغ المستحق', compute='_compute_amount_due', store=True)
    payment_state = fields.Selection([
        ('unpaid', 'غير مدفوعة'),
        ('partial', 'مدفوعة جزئياً'),
        ('paid', 'مدفوعة كاملاً'),
    ], string='حالة الدفع', compute='_compute_payment_state', store=True)

    @api.depends('total_value', 'amount_paid')
    def _compute_amount_due(self):
        for rec in self:
            rec.amount_due = rec.total_value - rec.amount_paid

    @api.depends('total_value', 'amount_paid')
    def _compute_payment_state(self):
        for rec in self:
            if rec.amount_paid <= 0:
                rec.payment_state = 'unpaid'
            elif rec.amount_paid >= rec.total_value:
                rec.payment_state = 'paid'
            else:
                rec.payment_state = 'partial'

    def action_receive(self):
        for record in self:
            if not record.destination_location_id:
                raise UserError(_('Please select a destination location first.'))
            if not record.line_ids:
                raise UserError(_('Please add at least one product.'))

            source_location = self.env.ref('stock.stock_location_suppliers', raise_if_not_found=False)
            if not source_location:
                source_location = self.env['stock.location'].search(
                    [('usage', '=', 'supplier')], limit=1)
            if not source_location:
                raise UserError(_('No supplier location found. Please configure your warehouse.'))

            for line in record.line_ids:
                if not line.product_id:
                    continue

                product = line.product_id
                # Check if product tracks inventory (is storable)
                is_tracked = (
                    product.type in ('product', 'storable') or
                    getattr(product, 'is_storable', False)
                )
                if not is_tracked:
                    # Auto-convert to storable
                    try:
                        product.product_tmpl_id.sudo().write({'type': 'storable'})
                    except Exception:
                        raise UserError(
                            _('Product "%s" cannot be set as Storable. '
                              'Please change its Product Type manually.') % product.name
                        )

                move = self.env['stock.move'].sudo().create({
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_uom_id.id,
                    'location_id': source_location.id,
                    'location_dest_id': record.destination_location_id.id,
                    'description_picking': record.name or '/',
                    'state': 'draft',
                })
                move._action_confirm()
                move._action_assign()

                if move.move_line_ids:
                    move.move_line_ids.write({'quantity': line.quantity, 'picked': True})
                else:
                    self.env['stock.move.line'].sudo().create({
                        'move_id': move.id,
                        'product_id': line.product_id.id,
                        'quantity': line.quantity,
                        'product_uom_id': line.product_uom_id.id,
                        'location_id': source_location.id,
                        'location_dest_id': record.destination_location_id.id,
                        'picked': True,
                    })
                move._action_done()

            record.state = 'done'

            # تسجيل في حساب المورد تلقائياً
            if record.vendor_id and record.total_value > 0:
                vendor_account = self.env['medical.vendor.account'].get_or_create(record.vendor_id.id)
                # إضافة سطر مشتريات
                existing = self.env['medical.vendor.account.line'].search([
                    ('receive_id', '=', record.id)
                ])
                if not existing:
                    self.env['medical.vendor.account.line'].create({
                        'vendor_account_id': vendor_account.id,
                        'date': record.date_receive,
                        'line_type': 'purchase',
                        'amount': record.total_value,
                        'reference': record.name,
                        'receive_id': record.id,
                        'notes': record.vendor_invoice_ref or '',
                    })
                # تسجيل الدفعة الفورية لو فيه
                if record.amount_paid > 0:
                    payment = self.env['medical.vendor.payment'].create({
                        'vendor_account_id': vendor_account.id,
                        'date': record.date_receive,
                        'amount': record.amount_paid,
                        'reference': record.name,
                        'receive_id': record.id,
                        'notes': 'دفعة فورية عند الاستلام',
                    })
                    payment.action_confirm()
            record.message_post(body=_('Stock received successfully into %s.') %
                                record.destination_location_id.name)



    def action_print_receipt(self):
        """فتح صفحة الطباعة في نافذة جديدة"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/medical_inventory/receipt/{self.id}',
            'target': 'new',
        }

    def action_view_vendor_account(self):
        """زرار عرض حساب المورد من الاستلام"""
        self.ensure_one()
        account = self.env['medical.vendor.account'].search([
            ('vendor_id', '=', self.vendor_id.id)
        ], limit=1)
        if not account:
            return
        return {
            'name': 'حساب %s' % self.vendor_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'medical.vendor.account',
            'res_id': account.id,
            'view_mode': 'form',
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

    receive_id = fields.Many2one('medical.stock.receive', ondelete='cascade')

    # Stored related fields for analytics
    date_receive = fields.Date(related='receive_id.date_receive', string='Date', store=True)
    vendor_id = fields.Many2one('res.partner', related='receive_id.vendor_id',
                                string='Vendor', store=True)
    destination_location_id = fields.Many2one('stock.location',
                                              related='receive_id.destination_location_id',
                                              string='Location', store=True)

    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    unit_price = fields.Float(string='Unit Price')
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', readonly=False)
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number')
    expiry_date = fields.Date(string='Expiry Date')
    notes = fields.Char(string='Notes')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.standard_price

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price