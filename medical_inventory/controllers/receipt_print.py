from odoo import http
from odoo.http import request
import json


class ReceiptPrintController(http.Controller):

    @http.route('/medical_inventory/receipt/<int:receipt_id>', type='http', auth='user')
    def print_receipt(self, receipt_id, **kwargs):
        receipt = request.env['medical.stock.receive'].sudo().browse(receipt_id)
        if not receipt.exists():
            return request.not_found()

        lines_html = ''
        for i, line in enumerate(receipt.line_ids):
            bg = '#f8fafc' if i % 2 == 0 else 'white'
            lines_html += f'''
            <tr style="background:{bg}">
                <td style="padding:8px;border:1px solid #e2e8f0;text-align:center">{i+1}</td>
                <td style="padding:8px;border:1px solid #e2e8f0;font-weight:bold">{line.product_id.name}</td>
                <td style="padding:8px;border:1px solid #e2e8f0;text-align:center">{line.quantity}</td>
                <td style="padding:8px;border:1px solid #e2e8f0;text-align:center">{line.product_uom_id.name}</td>
                <td style="padding:8px;border:1px solid #e2e8f0;text-align:center">{line.unit_price:.2f}</td>
                <td style="padding:8px;border:1px solid #e2e8f0;text-align:center;font-weight:bold">{line.subtotal:.2f}</td>
                <td style="padding:8px;border:1px solid #e2e8f0;text-align:center">{line.expiry_date or '—'}</td>
            </tr>'''

        vendor_name = receipt.vendor_id.name if receipt.vendor_id else (receipt.vendor_name or '—')
        company = request.env.company

        balance_html = ''
        if receipt.vendor_id:
            balance_html = f'''
            <tr><td style="padding:4px 8px;font-weight:bold;color:#64748b">الرصيد القديم:</td>
                <td style="padding:4px 8px;color:#0369a1">{receipt.vendor_old_balance:.2f} EGP</td></tr>
            <tr><td style="padding:4px 8px;font-weight:bold;color:#64748b">قيمة هذا الاستلام:</td>
                <td style="padding:4px 8px;color:#1565c0">+ {receipt.total_value:.2f} EGP</td></tr>
            {'<tr><td style="padding:4px 8px;font-weight:bold;color:#64748b">المدفوع الآن:</td><td style="padding:4px 8px;color:#15803d">- ' + f"{receipt.amount_paid:.2f} EGP</td></tr>" if receipt.amount_paid > 0 else ""}
            <tr style="border-top:2px solid #1565c0">
                <td style="padding:6px 8px;font-weight:bold;color:#64748b">الرصيد الجديد:</td>
                <td style="padding:6px 8px;font-weight:bold;font-size:16px;color:#c2410c">{receipt.vendor_new_balance:.2f} EGP</td>
            </tr>'''

        html = f'''<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<title>إيصال استلام - {receipt.name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; direction: rtl; padding: 20px; color: #1e293b; }}
  @media print {{
    .no-print {{ display: none !important; }}
    body {{ padding: 0; }}
  }}
  .btn {{ padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; margin: 5px; }}
  .btn-blue {{ background: #1565c0; color: white; }}
  .btn-green {{ background: #15803d; color: white; }}
</style>
</head>
<body>

<!-- أزرار الطباعة والتحميل -->
<div class="no-print" style="text-align:center;margin-bottom:20px;padding:15px;background:#f1f5f9;border-radius:8px;">
  <button class="btn btn-blue" onclick="window.print()">🖨️ طباعة / حفظ كـ PDF</button>
  <button class="btn btn-green" onclick="window.close()">✕ إغلاق</button>
  <p style="margin-top:8px;color:#64748b;font-size:13px;">
    للحفظ كـ PDF: اضغط طباعة ← اختر "Save as PDF" أو "Microsoft Print to PDF"
  </p>
</div>

<div style="max-width:900px;margin:0 auto;">

  <!-- العنوان -->
  <div style="text-align:center;margin-bottom:20px;border-bottom:2px solid #1565c0;padding-bottom:10px;">
    <h2 style="color:#1565c0;margin:0;">🏥 إيصال استلام مخزون</h2>
    <h3 style="margin:5px 0;">{receipt.name}</h3>
    <p style="color:#64748b">{company.name}</p>
  </div>

  <!-- معلومات الاستلام والمورد -->
  <div style="display:flex;gap:16px;margin-bottom:20px;">
    <div style="flex:1;background:#f8fafc;padding:12px;border-radius:6px;">
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:4px 8px;font-weight:bold;color:#64748b">التاريخ:</td>
            <td style="padding:4px 8px">{receipt.date_receive}</td></tr>
        <tr><td style="padding:4px 8px;font-weight:bold;color:#64748b">استلم بواسطة:</td>
            <td style="padding:4px 8px">{receipt.received_by.name}</td></tr>
        <tr><td style="padding:4px 8px;font-weight:bold;color:#64748b">موقع التخزين:</td>
            <td style="padding:4px 8px">{receipt.destination_location_id.name}</td></tr>
        {'<tr><td style="padding:4px 8px;font-weight:bold;color:#64748b">مرجع الفاتورة:</td><td style="padding:4px 8px">' + receipt.vendor_invoice_ref + '</td></tr>' if receipt.vendor_invoice_ref else ''}
      </table>
    </div>
    <div style="flex:1;background:#f8fafc;padding:12px;border-radius:6px;">
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:4px 8px;font-weight:bold;color:#64748b">المورد:</td>
            <td style="padding:4px 8px;font-weight:bold">{vendor_name}</td></tr>
        {balance_html}
      </table>
    </div>
  </div>

  <!-- جدول المنتجات -->
  <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
    <thead>
      <tr style="background:#1565c0;color:white;">
        <th style="padding:10px;border:1px solid #1565c0">#</th>
        <th style="padding:10px;border:1px solid #1565c0;text-align:right">المنتج</th>
        <th style="padding:10px;border:1px solid #1565c0">الكمية</th>
        <th style="padding:10px;border:1px solid #1565c0">الوحدة</th>
        <th style="padding:10px;border:1px solid #1565c0">سعر الوحدة</th>
        <th style="padding:10px;border:1px solid #1565c0">الإجمالي</th>
        <th style="padding:10px;border:1px solid #1565c0">تاريخ الانتهاء</th>
      </tr>
    </thead>
    <tbody>{lines_html}</tbody>
    <tfoot>
      <tr style="background:#1e293b;color:white;font-weight:bold;">
        <td colspan="5" style="padding:10px;border:1px solid #1e293b">الإجمالي الكلي</td>
        <td style="padding:10px;border:1px solid #1e293b;text-align:center;font-size:16px">{receipt.total_value:.2f} EGP</td>
        <td style="border:1px solid #1e293b"></td>
      </tr>
    </tfoot>
  </table>

  <!-- ملخص الدفع -->
  <div style="display:flex;justify-content:flex-end;margin-bottom:20px;">
    <div style="min-width:300px;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
      <div style="background:#f1f5f9;padding:8px 12px;font-weight:bold;border-bottom:1px solid #e2e8f0">ملخص الدفع</div>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:8px 12px;color:#64748b">قيمة الفاتورة:</td>
            <td style="padding:8px 12px;font-weight:bold">{receipt.total_value:.2f} EGP</td></tr>
        <tr style="background:#f8fafc">
            <td style="padding:8px 12px;color:#64748b">المدفوع الآن:</td>
            <td style="padding:8px 12px;color:#15803d;font-weight:bold">{receipt.amount_paid:.2f} EGP</td></tr>
        <tr style="border-top:2px solid #e2e8f0">
            <td style="padding:10px 12px;font-weight:bold">المتبقي:</td>
            <td style="padding:10px 12px;font-weight:bold;color:#c2410c;font-size:15px">{receipt.amount_due:.2f} EGP</td></tr>
      </table>
    </div>
  </div>

  <!-- التوقيعات -->
  <div style="display:flex;justify-content:space-between;margin-top:50px;padding-top:20px;border-top:1px solid #e2e8f0;">
    <div style="text-align:center;width:30%">
      <div style="border-top:1px solid #333;padding-top:5px;margin-top:40px">توقيع المستلم</div>
    </div>
    <div style="text-align:center;width:30%">
      <div style="border-top:1px solid #333;padding-top:5px;margin-top:40px">توقيع المورد</div>
    </div>
    <div style="text-align:center;width:30%">
      <div style="border-top:1px solid #333;padding-top:5px;margin-top:40px">توقيع المدير</div>
    </div>
  </div>

</div>
</body>
</html>'''

        return request.make_response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
        ])
