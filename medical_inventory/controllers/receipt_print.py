from odoo import http, fields
from odoo.http import request

class ReceiptPrintController(http.Controller):

    # 1. إيصال استلام الموردين (الشكل الكامل بالبيانات المالية والتوقيعات)
    @http.route('/medical_inventory/receipt/<int:receipt_id>', type='http', auth='user')
    def print_receipt(self, receipt_id, **kwargs):
        receipt = request.env['medical.stock.receive'].sudo().browse(receipt_id)
        if not receipt.exists(): return request.not_found()

        lines_html = ''
        for i, line in enumerate(receipt.line_ids):
            bg = '#ffffff' if i % 2 == 0 else '#f9f9f9'
            lines_html += f'''
            <tr style="background:{bg}">
                <td style="padding:10px; border:1px solid #333;">{i + 1}</td>
                <td style="padding:10px; border:1px solid #333; text-align:right;">{line.product_id.name}</td>
                <td style="padding:10px; border:1px solid #333;">{line.quantity} {line.product_uom_id.name}</td>
                <td style="padding:10px; border:1px solid #333;">{line.unit_price:,.2f}</td>
                <td style="padding:10px; border:1px solid #333; font-weight:bold;">{line.subtotal:,.2f}</td>
            </tr>'''

        vendor_name = receipt.vendor_id.name if receipt.vendor_id else (receipt.vendor_name or '—')

        html = f'''<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Arial', sans-serif; margin: 0; padding: 40px; color: #333; }}
        .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #000; padding-bottom: 10px; }}
        .info-table {{ width: 100%; margin-bottom: 20px; }}
        .info-table td {{ padding: 5px; vertical-align: top; }}
        .main-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .main-table th {{ background: #eee; padding: 10px; border: 1px solid #000; }}
        .balance-box {{ float: left; width: 300px; margin-top: 20px; border: 1px solid #000; padding: 10px; }}
        .balance-box td {{ padding: 5px; }}
        .signatures {{ margin-top: 60px; display: flex; justify-content: space-between; text-align: center; }}
        .sig-box {{ width: 30%; border-top: 1px solid #000; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>إيصال استلام مخزون من مورد</h1>
        <h2>{receipt.name}</h2>
    </div>

    <table class="info-table">
        <tr>
            <td style="width: 50%;"><b>المورد:</b> {vendor_name}</td>
            <td style="text-align: left;"><b>التاريخ:</b> {receipt.date_receive}</td>
        </tr>
        <tr>
            <td><b>المستودع المستلم:</b> {receipt.destination_location_id.name}</td>
            <td style="text-align: left;"><b>الشركة:</b> {request.env.company.name}</td>
        </tr>
    </table>

    <table class="main-table">
        <thead>
            <tr>
                <th>#</th>
                <th>الصنف / البيان</th>
                <th>الكمية</th>
                <th>سعر الوحدة</th>
                <th>الإجمالي</th>
            </tr>
        </thead>
        <tbody>{lines_html}</tbody>
    </table>

    <div class="balance-box">
        <table style="width: 100%;">
            <tr><td>الرصيد القديم:</td><td style="text-align: left;">{receipt.vendor_old_balance:,.2f}</td></tr>
            <tr><td>قيمة الاستلام:</td><td style="text-align: left; color: blue;">+ {receipt.total_value:,.2f}</td></tr>
            <tr><td>المبلغ المدفوع:</td><td style="text-align: left; color: green;">- {receipt.amount_paid:,.2f}</td></tr>
            <tr style="font-weight: bold; border-top: 1px solid #000;">
                <td>الرصيد الجديد:</td><td style="text-align: left; color: red;">{receipt.vendor_new_balance:,.2f}</td>
            </tr>
        </table>
    </div>

    <div style="clear: both;"></div>

    <div class="signatures">
        <div class="sig-box">توقيع المورد</div>
        <div class="sig-box">أمين المخزن</div>
        <div class="sig-box">اعتماد الإدارة</div>
    </div>

    <script>window.onload = function() {{ window.print(); }}</script>
</body>
</html>'''
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])

    # 2. طباعة طلب النقل أو الاستهلاك (الفصل في المسميات والتوقيعات)
    @http.route('/medical_inventory/transfer_print/<int:request_id>', type='http', auth='user')
    def print_transfer(self, request_id, **kwargs):
        req = request.env['medical.consumption.request'].sudo().browse(request_id)
        if not req.exists(): return request.not_found()

        is_consumption = req.request_type == 'consumption'
        title = "تقرير استهلاك أصناف طبية" if is_consumption else "إذن صرف وتحويل مخزني"
        sign_label = "المسؤول عن العيادة" if is_consumption else "الموظف المستلم"

        lines_html = ''
        for i, line in enumerate(req.line_ids):
            lines_html += f'''
            <tr>
                <td style="padding:10px; border:1px solid #000;">{i + 1}</td>
                <td style="padding:10px; border:1px solid #000; text-align:right;">{line.product_id.name}</td>
                <td style="padding:10px; border:1px solid #000;">{line.quantity}</td>
                <td style="padding:10px; border:1px solid #000;">{line.product_uom_id.name}</td>
                <td style="padding:10px; border:1px solid #000;">{line.notes or ""}</td>
            </tr>'''

        html = f'''<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Arial', sans-serif; padding: 40px; }}
        .header {{ text-align: center; border-bottom: 3px double #000; margin-bottom: 20px; padding-bottom: 10px; }}
        .info {{ margin-bottom: 30px; font-size: 18px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #f2f2f2; padding: 10px; border: 1px solid #000; }}
        .footer-sig {{ margin-top: 80px; display: flex; justify-content: space-between; }}
        .box {{ width: 40%; text-align: center; border-top: 2px solid #000; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <h3>رقم المرجع: {req.name}</h3>
    </div>

    <div class="info">
        <p><b>التاريخ:</b> {req.date_request}</p>
        <p><b>الجهة / العيادة:</b> {req.department_location_id.name}</p>
        <p><b>المسؤول:</b> {req.requested_by.name}</p>
        {'<p><b>سحب من مستودع:</b> ' + req.source_location_id.name + '</p>' if not is_consumption else ''}
    </div>

    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>الصنف / المنتج</th>
                <th>الكمية</th>
                <th>الوحدة</th>
                <th>ملاحظات</th>
            </tr>
        </thead>
        <tbody>{lines_html}</tbody>
    </table>

    <div class="footer-sig">
        <div class="box">{sign_label}</div>
        <div class="box">اعتماد المدير / المراجع</div>
    </div>

    <script>window.onload = function() {{ window.print(); }}</script>
</body>
</html>'''
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])