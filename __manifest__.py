{
    'name': 'Bakery Management',
    'version':'1.0',
    'summary': 'Manage bakery',
    'description': 'A module to manage bakery records, and related information.',
    'category': 'Food',
    'author': 'Kayondo',
    'depends': ['base','mail','sale','account'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_payment.xml',
        'views/view_transaction_id.xml',
        'views/account_invoice_view.xml',
        'views/vat_product_view.xml'
    ],
    'installable': True,
    'application': True,
}
