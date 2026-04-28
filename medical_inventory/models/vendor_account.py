from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MedicalVendorAccount(models.Model):
    _name = 'medical.vendor.account'
    _description = 'حساب المورد'
    _inherit = ['mail.thread']
    _order = 'vendor_id'

    vendor_id = fields.Many2one('res.partner', string='المورد', required=True,
                                 ondelete='restrict', tracking=True)
    currency_id = fields.Many2one('res.currency', string='العملة',
                                   default=lambda self: self.env.company.currency_id)

    total_purchases = fields.Float(string='إجمالي المشتريات',
                                    compute='_compute_balances', store=True)
    total_paid = fields.Float(string='إجمالي المدفوع',
                               compute='_compute_balances', store=True)
    balance_due = fields.Float(string='الرصيد المستحق',
                                compute='_compute_balances', store=True)

    receive_ids = fields.One2many('medical.stock.receive', 'vendor_id',
                                   string='الاستلامات')
    payment_ids = fields.One2many('medical.vendor.payment', 'vendor_account_id',
                                   string='الدفعات')
    line_ids = fields.One2many('medical.vendor.account.line', 'vendor_account_id',
                                string='حركات الحساب')

    receive_count = fields.Integer(compute='_compute_counts', string='عدد الاستلامات')
    payment_count = fields.Integer(compute='_compute_counts', string='عدد الدفعات')
    notes = fields.Text(string='ملاحظات')

    _sql_constraints = [
        ('vendor_unique', 'UNIQUE(vendor_id)', 'يوجد حساب لهذا المورد بالفعل!')
    ]

    @api.depends('line_ids.amount', 'line_ids.line_type')
    def _compute_balances(self):
        for rec in self:
            purchases = sum(l.amount for l in rec.line_ids if l.line_type == 'purchase')
            payments = sum(l.amount for l in rec.line_ids if l.line_type == 'payment')
            rec.total_purchases = purchases
            rec.total_paid = payments
            rec.balance_due = purchases - payments

    @api.depends('receive_ids', 'payment_ids')
    def _compute_counts(self):
        for rec in self:
            rec.receive_count = len(rec.receive_ids.filtered(lambda r: r.state == 'done'))
            rec.payment_count = len(rec.payment_ids)

    def action_view_receives(self):
        return {
            'name': 'استلامات %s' % self.vendor_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'medical.stock.receive',
            'view_mode': 'list,form',
            'domain': [('vendor_id', '=', self.vendor_id.id), ('state', '=', 'done')],
        }

    def action_view_payments(self):
        return {
            'name': 'دفعات %s' % self.vendor_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'medical.vendor.payment',
            'view_mode': 'list,form',
            'domain': [('vendor_account_id', '=', self.id)],
            'context': {'default_vendor_account_id': self.id},
        }

    def action_register_payment(self):
        return {
            'name': 'تسجيل دفعة',
            'type': 'ir.actions.act_window',
            'res_model': 'medical.vendor.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vendor_account_id': self.id,
                'default_vendor_id': self.vendor_id.id,
                'default_amount': self.balance_due,
            },
        }

    @api.model
    def get_or_create(self, vendor_id):
        """جلب أو إنشاء حساب للمورد — دايما بيرجع نفس الحساب"""
        account = self.search([('vendor_id', '=', vendor_id)], limit=1)
        if not account:
            account = self.create({'vendor_id': vendor_id})
        return account

    @api.model
    def get_vendor_balance(self, vendor_id):
        """جلب الرصيد الحالي للمورد"""
        account = self.search([('vendor_id', '=', vendor_id)], limit=1)
        if account:
            return {
                'balance_due': account.balance_due,
                'total_purchases': account.total_purchases,
                'total_paid': account.total_paid,
            }
        return {'balance_due': 0.0, 'total_purchases': 0.0, 'total_paid': 0.0}


class MedicalVendorAccountLine(models.Model):
    _name = 'medical.vendor.account.line'
    _description = 'حركة حساب المورد'
    _order = 'date asc, id asc'

    vendor_account_id = fields.Many2one('medical.vendor.account', ondelete='cascade',
                                         string='حساب المورد')
    date = fields.Date(string='التاريخ', required=True, default=fields.Date.context_today)
    line_type = fields.Selection([
        ('purchase', 'مشتريات'),
        ('payment', 'دفعة'),
    ], string='النوع', required=True)
    amount = fields.Float(string='المبلغ', required=True)
    reference = fields.Char(string='المرجع')
    notes = fields.Char(string='ملاحظات')
    receive_id = fields.Many2one('medical.stock.receive', string='الاستلام')
    payment_id = fields.Many2one('medical.vendor.payment', string='الدفعة')
    balance_after = fields.Float(string='الرصيد بعد', compute='_compute_balance_after', store=True)

    @api.depends('vendor_account_id', 'vendor_account_id.line_ids',
                 'date', 'amount', 'line_type')
    def _compute_balance_after(self):
        for rec in self:
            if not rec.vendor_account_id:
                rec.balance_after = 0
                continue
            lines = rec.vendor_account_id.line_ids.sorted(key=lambda l: (l.date, l.id))
            balance = 0
            for line in lines:
                if line.line_type == 'purchase':
                    balance += line.amount
                else:
                    balance -= line.amount
                if line.id == rec.id:
                    break
            rec.balance_after = balance


class MedicalVendorPayment(models.Model):
    _name = 'medical.vendor.payment'
    _description = 'دفعة المورد'
    _inherit = ['mail.thread']
    _order = 'date desc'

    name = fields.Char(string='رقم الدفعة', readonly=True, copy=False,
                        default=lambda self: self.env['ir.sequence'].next_by_code('medical.vendor.payment'))
    vendor_account_id = fields.Many2one('medical.vendor.account', string='حساب المورد',
                                         required=True, ondelete='restrict')
    vendor_id = fields.Many2one(related='vendor_account_id.vendor_id', string='المورد', store=True)
    date = fields.Date(string='تاريخ الدفع', required=True, default=fields.Date.context_today)
    amount = fields.Float(string='المبلغ المدفوع', required=True)
    payment_method = fields.Selection([
        ('cash', 'نقدي'),
        ('bank', 'تحويل بنكي'),
        ('check', 'شيك'),
        ('other', 'أخرى'),
    ], string='طريقة الدفع', default='cash')
    reference = fields.Char(string='المرجع / رقم الشيك')
    notes = fields.Text(string='ملاحظات')
    receive_id = fields.Many2one('medical.stock.receive', string='مقابل فاتورة')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
    ], default='draft', string='الحالة', tracking=True)

    def action_confirm(self):
        for rec in self:
            if rec.amount <= 0:
                raise UserError('المبلغ يجب أن يكون أكبر من صفر!')
            existing = self.env['medical.vendor.account.line'].search([
                ('payment_id', '=', rec.id)
            ])
            if not existing:
                self.env['medical.vendor.account.line'].create({
                    'vendor_account_id': rec.vendor_account_id.id,
                    'date': rec.date,
                    'line_type': 'payment',
                    'amount': rec.amount,
                    'reference': rec.name,
                    'notes': rec.notes or '',
                    'payment_id': rec.id,
                })
            rec.state = 'confirmed'
            rec.message_post(body='تم تأكيد الدفعة بمبلغ %.2f' % rec.amount)

    def action_reset_draft(self):
        for rec in self:
            self.env['medical.vendor.account.line'].search([
                ('payment_id', '=', rec.id)
            ]).unlink()
            rec.state = 'draft'
