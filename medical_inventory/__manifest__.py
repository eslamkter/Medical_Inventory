{
    'name': 'Medical Center Inventory',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Medical inventory with consumption requests, expiry tracking, and low stock alerts',
    'depends': ['stock', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/product_category_data.xml',
        'data/stock_location_data.xml',
        'data/ir_sequence_data.xml',
        'views/consumption_request_views.xml',
        'views/stock_alert_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
