from odoo import models, fields, api


class MedicalStockCard(models.Model):
    """كارتة الصنف - تتبع كل حركات المخزون لكل منتج"""
    _name = 'medical.stock.card'
    _description = 'كارتة الصنف'
    _auto = False
    _order = 'date desc, id desc'

    product_id = fields.Many2one('product.product', string='المنتج', readonly=True)
    product_name = fields.Char(string='اسم المنتج', readonly=True)
    date = fields.Date(string='التاريخ', readonly=True)
    move_type = fields.Selection([
        ('in', 'وارد'),
        ('out', 'صادر'),
    ], string='نوع الحركة', readonly=True)
    quantity = fields.Float(string='الكمية', readonly=True)
    location_id = fields.Many2one('stock.location', string='الموقع', readonly=True)
    reference = fields.Char(string='المرجع', readonly=True)
    source = fields.Char(string='المصدر', readonly=True)
    unit_price = fields.Float(string='سعر الوحدة', readonly=True)
    total_value = fields.Float(string='القيمة', readonly=True)
    balance_qty = fields.Float(string='رصيد الكمية', readonly=True)
    vendor_id = fields.Many2one('res.partner', string='المورد', readonly=True)
    uom = fields.Char(string='الوحدة', readonly=True)

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS medical_stock_card CASCADE")
        self.env.cr.execute("""
            CREATE VIEW medical_stock_card AS

            -- حركات الوارد (استلام من موردين)
            SELECT
                sm.id AS id,
                pp.id AS product_id,
                COALESCE(pt.name->>'ar_001', pt.name->>'en_US', '') AS product_name,
                sm.date::date AS date,
                'in'::varchar AS move_type,
                sml.quantity AS quantity,
                sl_dest.id AS location_id,
                COALESCE(msr.name, sm.origin, '/') AS reference,
                COALESCE(rp.name, msr.vendor_name, 'استلام') AS source,
                COALESCE(msrl.unit_price, 0.0) AS unit_price,
                COALESCE(msrl.subtotal, 0.0) AS total_value,
                rp.id AS vendor_id,
                COALESCE(uu.name->>'ar_001', uu.name->>'en_US', '') AS uom,
                SUM(sml.quantity) OVER (
                    PARTITION BY pp.id, sl_dest.id
                    ORDER BY sm.date, sm.id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS balance_qty
            FROM stock_move sm
            JOIN stock_move_line sml ON sml.move_id = sm.id
            JOIN product_product pp ON pp.id = sm.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            LEFT JOIN uom_uom uu ON uu.id = pt.uom_id
            JOIN stock_location sl_dest ON sl_dest.id = sm.location_dest_id
            JOIN stock_location sl_src ON sl_src.id = sm.location_id
            LEFT JOIN medical_stock_receive msr ON msr.name = sm.origin
            LEFT JOIN medical_stock_receive_line msrl ON msrl.receive_id = msr.id
                AND msrl.product_id = pp.id
            LEFT JOIN res_partner rp ON rp.id = msr.vendor_id
            WHERE sl_dest.usage = 'internal'
              AND sl_src.usage != 'internal'
              AND sm.state = 'done'

            UNION ALL

            -- حركات الصادر (صرف للعيادات)
            SELECT
                sm.id + 10000000 AS id,
                pp.id AS product_id,
                COALESCE(pt.name->>'ar_001', pt.name->>'en_US', '') AS product_name,
                sm.date::date AS date,
                'out'::varchar AS move_type,
                sml.quantity AS quantity,
                sl_src.id AS location_id,
                COALESCE(mcr.name, sm.origin, '/') AS reference,
                COALESCE('صرف - ' || sl_dest.name, 'صرف') AS source,
                0.0 AS unit_price,
                0.0 AS total_value,
                NULL::integer AS vendor_id,
                COALESCE(uu.name->>'ar_001', uu.name->>'en_US', '') AS uom,
                -SUM(sml.quantity) OVER (
                    PARTITION BY pp.id, sl_src.id
                    ORDER BY sm.date, sm.id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS balance_qty
            FROM stock_move sm
            JOIN stock_move_line sml ON sml.move_id = sm.id
            JOIN product_product pp ON pp.id = sm.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            LEFT JOIN uom_uom uu ON uu.id = pt.uom_id
            JOIN stock_location sl_src ON sl_src.id = sm.location_id
            JOIN stock_location sl_dest ON sl_dest.id = sm.location_dest_id
            LEFT JOIN medical_consumption_request mcr ON mcr.name = sm.origin
            WHERE sl_src.usage = 'internal'
              AND sl_dest.usage != 'internal'
              AND sm.state = 'done'
        """)
