{
    'name': "Villa Nova - ITAM (Gestion des actifs)",
    'summary': (
        "Gestion des actifs informatiques natif Odoo Community : materiel "
        "(construit sur le module Maintenance natif - categories, garantie, "
        "cycle de vie, cout), logiciels (licences, sieges, conformite) et "
        "ESAM/Endpoint (posture de securite, statut endpoint, decouverte "
        "via un point d'entree API reel), relies aux tickets du Service "
        "Desk. Integre dans l'app ITSM (pas d'application separee) pour un "
        "espace de travail unifie façon ServiceDesk Plus. Phases 4-5 de la "
        "plateforme ITSM complete construite phase par phase."
    ),
    'version': '18.0.1.1.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['maintenance', 'hr', 'hr_maintenance', 'villa_nova_itsm'],
    'data': [
        'security/itam_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/itam_discovery_data.xml',
        'views/itam_asset_views.xml',
        'views/itam_endpoint_views.xml',
        'views/itam_software_views.xml',
        'views/itsm_ticket_itam_views.xml',
        'views/itam_menus.xml',
    ],
    'demo': [
        'demo/itam_demo.xml',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init',
}
