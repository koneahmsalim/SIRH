{
    'name': "Villa Nova - Analytique & Rapports",
    'summary': (
        "Tableau de bord gestionnaire (conformite SLA, tendance des "
        "tickets, temps de resolution par priorite, top categories, "
        "satisfaction client, conformite des actifs, taux de succes des "
        "changements) et vues pivot/graphique natives sur les tickets et "
        "changements pour l'analyse ad-hoc. Integre dans l'app ITSM "
        "unifiee. Phase 10 de la plateforme ITSM complete construite "
        "phase par phase."
    ),
    'version': '18.0.1.0.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['villa_nova_change', 'villa_nova_knowledge'],
    'data': [
        'views/itsm_ticket_pivot_views.xml',
        'views/itsm_change_pivot_views.xml',
        'views/analytics_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'villa_nova_analytics/static/src/analytics_dashboard/analytics_dashboard.scss',
            'villa_nova_analytics/static/src/analytics_dashboard/analytics_dashboard.xml',
            'villa_nova_analytics/static/src/analytics_dashboard/analytics_dashboard.js',
        ],
    },
    'installable': True,
    'application': False,
}
