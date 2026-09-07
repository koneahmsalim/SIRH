{
    'name': "Villa Nova - CMDB (Base de gestion de configuration)",
    'summary': (
        "CMDB natif Odoo Community : relations typees entre elements de "
        "configuration (actifs materiels, services) - depend de/heberge "
        "sur/connecte a/fait partie de - et analyse d'impact reelle "
        "(si ce CI tombe en panne, qu'est-ce qui est affecte, avec les "
        "tickets ouverts correspondants). Integre dans l'app ITSM "
        "unifiee (pas d'application separee). Phase 6 de la plateforme "
        "ITSM complete construite phase par phase."
    ),
    'version': '18.0.1.0.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['villa_nova_itsm', 'villa_nova_itam'],
    'data': [
        'security/ir.model.access.csv',
        'views/cmdb_relation_views.xml',
        'views/cmdb_ci_views.xml',
        'views/cmdb_menus.xml',
    ],
    'demo': [
        'demo/cmdb_demo.xml',
    ],
    'installable': True,
    'application': False,
}
