{
    'name': "Villa Nova - Dashboard",
    'summary': (
        "Nouveau tableau de bord RH (OWL propre, sans dependance CDN) qui "
        "remplace l'interface du module hrms_dashboard tout en reutilisant "
        "integralement sa logique metier (models/hr_employee.py) : KPI "
        "cliquables, pointage, a-venir (anniversaires/evenements/annonces), "
        "graphiques en barres maison, dernieres demandes de conges/notes "
        "de frais."
    ),
    'version': '18.0.1.0.0',
    'category': 'Theme',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['web', 'villa_nova_theme', 'hrms_dashboard'],
    'data': [
        'views/dashboard_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'villa_nova_dashboard/static/src/bar_chart/bar_chart.js',
            'villa_nova_dashboard/static/src/bar_chart/bar_chart.xml',
            'villa_nova_dashboard/static/src/bar_chart/grouped_bar_chart.js',
            'villa_nova_dashboard/static/src/bar_chart/grouped_bar_chart.xml',
            'villa_nova_dashboard/static/src/dashboard/dashboard.scss',
            'villa_nova_dashboard/static/src/dashboard/dashboard.xml',
            'villa_nova_dashboard/static/src/dashboard/dashboard.js',
        ],
    },
    'installable': True,
    'application': False,
}
