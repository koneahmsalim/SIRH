{
    'name': "Villa Nova - Navigation",
    'summary': (
        "Navigation a deux niveaux : rail d'icones permanent (switcher "
        "d'applications) + panneau de sections contextuel en accordeon "
        "(une app a la fois, un groupe ouvert a la fois), a la place de la "
        "barre horizontale et du mega-menu app-switcher fourni par "
        "ohrms_core. Concu a partir d'une analyse de la profondeur reelle "
        "de navigation du projet (Employes : 13 categories / 51 elements). "
        "Barre superieure conservee mais allegee (systray uniquement). "
        "Montee de facon additive (registry main_components) sans toucher "
        "aux composants du coeur Odoo. Navigation mobile inchangee "
        "(reutilise les overlays natifs Odoo)."
    ),
    'version': '18.0.2.0.0',
    'category': 'Theme',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['web', 'bus', 'villa_nova_theme'],
    'assets': {
        'web.assets_backend': [
            'villa_nova_shell/static/src/sidebar/sidebar.scss',
            'villa_nova_shell/static/src/sidebar/shell_state.js',
            'villa_nova_shell/static/src/sidebar/sidebar.xml',
            'villa_nova_shell/static/src/sidebar/sidebar.js',
            'villa_nova_shell/static/src/sidebar/section_panel.xml',
            'villa_nova_shell/static/src/sidebar/section_panel.js',
            'villa_nova_shell/static/src/reload_watchdog/reload_watchdog_service.js',
        ],
    },
    'installable': True,
    'application': False,
}
