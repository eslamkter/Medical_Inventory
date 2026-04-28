from odoo import http, fields as odoo_fields
from odoo.http import request
from datetime import date, timedelta, datetime


class MedicalInventoryDashboard(http.Controller):

    @http.route('/medical_inventory/dashboard_data', type='json', auth='user')
    def dashboard_data(self):
        env = request.env
        # Reset any aborted transaction from previous failed requests
        env.cr.rollback()

        today = date.today()
        in_5 = today + timedelta(days=5)
        today_str = odoo_fields.Date.to_string(today)
        in_5_str = odoo_fields.Date.to_string(in_5)

        try:
            quants = env['stock.quant'].sudo().search([
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0),
            ])
            total_products = len(set(quants.mapped('product_id').ids))
            total_qty = sum(quants.mapped('quantity'))
            total_value = sum(q.quantity * (q.product_id.standard_price or 0) for q in quants)
        except Exception:
            env.cr.rollback()
            total_products = total_qty = total_value = 0

        try:
            pending = env['medical.consumption.request'].sudo().search_count([('state', '=', 'submitted')])
            approved = env['medical.consumption.request'].sudo().search_count([('state', '=', 'approved')])
        except Exception:
            env.cr.rollback()
            pending = approved = 0

        try:
            expired_count = env['medical.stock.receive.line'].sudo().search_count([
                ('expiry_date', '!=', False),
                ('expiry_date', '<=', today_str),
                ('receive_id.state', '=', 'done'),
            ])
            critical_count = env['medical.stock.receive.line'].sudo().search_count([
                ('expiry_date', '!=', False),
                ('expiry_date', '>', today_str),
                ('expiry_date', '<=', in_5_str),
                ('receive_id.state', '=', 'done'),
            ])
        except Exception:
            env.cr.rollback()
            expired_count = critical_count = 0

        try:
            receipts = env['medical.stock.receive'].sudo().search(
                [('state', '=', 'done')], order='date_receive desc', limit=5)
            receipts_data = []
            for r in receipts:
                try:
                    vendor = r.vendor_id.name if r.vendor_id else (r.vendor_name or 'Unknown')
                except Exception:
                    vendor = 'Unknown'
                receipts_data.append({
                    'name': r.name or '',
                    'date': r.date_receive.strftime('%d %b %Y') if r.date_receive else '',
                    'vendor': vendor,
                    'location': r.destination_location_id.name or '',
                    'value': round(r.total_value or 0, 2),
                })
        except Exception:
            env.cr.rollback()
            receipts_data = []

        try:
            locations = env['stock.location'].sudo().search([
                ('usage', '=', 'internal'), ('active', '=', True)
            ])
            loc_data = []
            for loc in locations:
                lq = env['stock.quant'].sudo().search([
                    ('location_id', '=', loc.id), ('quantity', '>', 0)
                ])
                qty = round(sum(lq.mapped('quantity')), 1)
                loc_val = round(sum(q.quantity * (q.product_id.standard_price or 0) for q in lq), 2)
                loc_data.append({
                    'name': loc.name,
                    'product_count': len(set(lq.mapped('product_id').ids)),
                    'total_qty': qty,
                    'total_value': loc_val,
                })
            loc_data.sort(key=lambda x: x['total_qty'], reverse=True)
        except Exception:
            env.cr.rollback()
            loc_data = []

        try:
            expiry_lines = env['medical.stock.receive.line'].sudo().search([
                ('expiry_date', '!=', False),
                ('expiry_date', '<=', in_5_str),
                ('receive_id.state', '=', 'done'),
            ], limit=50)
            expiry_items = []
            seen = set()
            for l in expiry_lines:
                try:
                    exp_date = l.expiry_date
                    if isinstance(exp_date, datetime):
                        exp_date = exp_date.date()
                    key = (l.product_id.id, str(exp_date))
                    if key in seen:
                        continue
                    seen.add(key)
                    days = (exp_date - today).days
                    expiry_items.append({
                        'product': l.product_id.name or '',
                        'qty': l.quantity,
                        'expiry': exp_date.strftime('%d %b %Y'),
                        'days_left': days,
                        'location': l.receive_id.destination_location_id.name or '',
                        'expired': days < 0,
                        'critical': 0 <= days <= 5,
                    })
                except Exception:
                    continue
            expiry_items.sort(key=lambda x: x['days_left'])
        except Exception:
            env.cr.rollback()
            expiry_items = []

        try:
            from dateutil.relativedelta import relativedelta
            monthly_spend = []
            for i in range(5, -1, -1):
                month_start = today.replace(day=1) - relativedelta(months=i)
                month_end = month_start + relativedelta(months=1)
                month_receipts = env['medical.stock.receive'].sudo().search([
                    ('state', '=', 'done'),
                    ('date_receive', '>=', odoo_fields.Date.to_string(month_start)),
                    ('date_receive', '<', odoo_fields.Date.to_string(month_end)),
                ])
                monthly_spend.append({
                    'month': month_start.strftime('%b %Y'),
                    'value': round(sum(r.total_value or 0 for r in month_receipts), 2),
                    'count': len(month_receipts),
                })
        except Exception:
            env.cr.rollback()
            monthly_spend = []

        try:
            all_lines = env['medical.stock.receive.line'].sudo().search([
                ('receive_id.state', '=', 'done')
            ])
            product_spend = {}
            for l in all_lines:
                pid = l.product_id.id
                if not pid:
                    continue
                if pid not in product_spend:
                    product_spend[pid] = {'name': l.product_id.name, 'total': 0, 'qty': 0}
                product_spend[pid]['total'] += (l.subtotal or 0)
                product_spend[pid]['qty'] += (l.quantity or 0)
            top_products = sorted(product_spend.values(), key=lambda x: x['total'], reverse=True)[:5]
            for p in top_products:
                p['total'] = round(p['total'], 2)
                p['qty'] = round(p['qty'], 1)
        except Exception:
            env.cr.rollback()
            top_products = []

        return {
            'total_products': total_products,
            'total_qty': round(total_qty, 0),
            'total_value': round(total_value, 2),
            'pending_requests': pending,
            'approved_requests': approved,
            'expired_count': expired_count,
            'critical_count': critical_count,
            'recent_receipts': receipts_data,
            'locations': loc_data[:10],
            'expiry_items': expiry_items,
            'monthly_spend': monthly_spend,
            'top_products': top_products,
        }
