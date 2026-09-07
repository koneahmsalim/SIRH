{
    'name': "Villa Nova - Problem / Change / Release Management",
    'summary': (
        "Gestion des problemes (analyse de cause racine, erreurs connues), "
        "des changements (workflow avec approbation CAB, evaluation du "
        "risque, plan de retour arriere) et des releases (regroupement de "
        "changements) - relies aux tickets et aux elements de configuration "
        "du CMDB. Integre dans l'app ITSM unifiee. Phase 7 de la plateforme "
        "ITSM complete construite phase par phase."
    ),
    'version': '18.0.1.0.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['villa_nova_cmdb'],
    'data': [
        'security/change_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/itsm_problem_views.xml',
        'views/itsm_change_views.xml',
        'views/itsm_release_views.xml',
        'views/itsm_ticket_problem_views.xml',
        'views/change_menus.xml',
    ],
    'demo': [
        'demo/change_demo.xml',
    ],
    'installable': True,
    'application': False,
}
