{
    'name': "Villa Nova - Theme Infinity Africa Group",
    'summary': (
        "Design system Infinity Africa Group : palette de marque (graphite + "
        "cramoisi, extraite du site officiel infinity-africa.com), paire "
        "typographique auto-hebergee (Manrope/Inter/JetBrains Mono), tokens "
        "d'espacement/rayon/ombre et composants de base (cartes, badges, "
        "etats vides, skeletons) appliques a tout le backend Odoo."
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
            ('before', 'web/static/src/scss/primary_variables.scss', 'villa_nova_theme/static/src/scss/typography_variables.scss'),
        ],
        'web.assets_backend': [
            'villa_nova_theme/static/src/scss/fonts.scss',
            'villa_nova_theme/static/src/scss/design_tokens.scss',
        ],
    },
    'installable': True,
    'application': False,
    'post_init_hook': 'set_company_branding',
}
