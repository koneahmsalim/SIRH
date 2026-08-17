{
    'name': "Villa Nova - Theme Infinity Africa Group",
    'summary': (
        "Identite visuelle de marque (graphite + cramoisi, extraite du site "
        "officiel infinity-africa.com) appliquee a tout le backend Odoo : "
        "barre superieure, boutons, liens, page de connexion, favicon."
    ),
    'version': '18.0.1.0.0',
    'category': 'Theme',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [
        'views/webclient_templates.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('before', 'web/static/src/scss/primary_variables.scss', 'villa_nova_theme/static/src/scss/primary_variables.scss'),
        ],
    },
    'installable': True,
    'application': False,
    'post_init_hook': 'set_company_branding',
}
