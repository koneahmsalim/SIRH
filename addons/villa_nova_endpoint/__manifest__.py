{
    'name': "Villa Nova - Endpoint Management (Agent RMM)",
    'summary': (
        "Gestion des postes par agent : inventaire materiel/logiciel/reseau "
        "complet remonte par un agent Windows reel (Go), enrolement securise "
        "par cle organisationnelle revocable, identite/secret unique par "
        "poste (jamais partages), check-in periodique. Console de parc "
        "(vues graph/pivot, alerte automatique sur poste hors ligne "
        "prolonge, rapprochement logiciels installes/licences suivies). "
        "Etend les actifs ITAM existants (maintenance.equipment) plutot que "
        "de dupliquer un modele parallele. Phases 2-3 (Agent MVP, Console "
        "de gestion) de la plateforme Endpoint Management/RMM construite "
        "phase par phase, apres les 12 phases ITSM."
    ),

    'icon': '/villa_nova_endpoint/static/description/icon.png',

    'version': '18.0.1.1.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['villa_nova_itam'],
    'data': [
        'security/ir.model.access.csv',
        'data/endpoint_cron_data.xml',
        'views/endpoint_agent_views.xml',
        'views/endpoint_enrollment_key_views.xml',
        'views/hardware_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/endpoint_menus.xml',
        'wizard/endpoint_enrollment_key_reveal_views.xml',
    ],
    'installable': True,
    'application': False,
}
