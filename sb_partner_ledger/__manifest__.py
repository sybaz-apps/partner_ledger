{
    'name': "Partner Ledger Report",
    'summary': "Partner Ledger and detail with items",
    'description': """
        Partner Ledger for a specific period and detail with item and quantity 
    """,
    "license": "LGPL-3",
    'author': "Muhammad Saleem",
    'website': "https://sybaz.com.pk/",
    'category': 'Accounting',
    'version': '19.0.1.0.1',
    'depends': ['account','base_accounting_kit','base_account_budget'],

    'data': [
        'security/ir.model.access.csv',
        'wizard/partner_ledger_wizard.xml',
        'views/partner_ledger_report_template.xml',
        'views/partner_ledger_report_detail_template.xml',
        'views/partner_ledger_report_template_pdf.xml',
        'views/partner_ledger_report_detail_template_pdf.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'price': 15,
    'currency': 'USD',
}
