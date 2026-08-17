{
    'name': "Villa Nova - Navigation",
    'summary': (
        "Sidebar persistante (applications + sections de l'app courante) a "
        "la place de la barre horizontale et du mega-menu app-switcher "
        "fourni par ohrms_core. Barre superieure conservee mais allegee "
        "(systray uniquement). Montee de facon additive (registry "
        "main_components) sans toucher aux composants du coeur Odoo. "
        "Navigation mobile inchangee (reutilise les overlays natifs Odoo)."
    ),
    'version': '18.0.1.0.0',
    'category': 'Theme',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['web', 'villa_nova_theme'],
    'assets': {
        'web.assets_backend': [
            'villa_nova_shell/static/src/sidebar/sidebar.scss',
            'villa_nova_shell/static/src/sidebar/sidebar.xml',
            'villa_nova_shell/static/src/sidebar/sidebar.js',
        ],
    },
    'installable': True,
    'application': False,
}
