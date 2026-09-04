{
    'name': "Villa Nova - ITAM (Gestion des actifs)",
    'summary': (
        "Gestion des actifs informatiques natif Odoo Community : materiel "
        "(construit sur le module Maintenance natif - categories, garantie, "
        "cycle de vie, cout) et logiciels (licences, sieges, conformite), "
        "relies aux tickets du Service Desk. Phase 4 de la plateforme ITSM "
        "complete construite phase par phase."
    ),
    'version': '18.0.1.0.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['maintenance', 'hr', 'hr_maintenance', 'villa_nova_itsm'],
    'data': [
        'security/itam_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/itam_asset_views.xml',
        'views/itam_software_views.xml',
        'views/itsm_ticket_itam_views.xml',
        'views/itam_menus.xml',
    ],
    'demo': [
        'demo/itam_demo.xml',
    ],
    'installable': True,
    'application': True,
    'post_init_hook': 'post_init',
}
