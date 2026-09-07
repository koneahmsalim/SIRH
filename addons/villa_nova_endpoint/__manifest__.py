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
        "de dupliquer un modele parallele. Actions a distance limitees a un "
        "catalogue FERME de commandes predefinies (jamais d'execution "
        "arbitraire), avec validation obligatoire par un second gestionnaire "
        "ITAM pour les actions sensibles (reutilise le moteur d'approbation "
        "existant) et audit complet par commande. Decouverte reseau (scan "
        "ping sweep nmap a la demande, rapprochement best-effort avec les "
        "actifs deja connus). Phases 2-5 (Agent MVP, Console de gestion, "
        "Actions a distance, Decouverte reseau) de la plateforme Endpoint "
        "Management/RMM construite phase par phase, apres les 12 phases "
        "ITSM."
    ),

    'icon': '/villa_nova_endpoint/static/description/icon.png',

    'version': '18.0.1.3.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['villa_nova_itam', 'villa_nova_change'],
    'data': [
        'security/ir.model.access.csv',
        'data/endpoint_cron_data.xml',
        'data/ir_sequence_data.xml',
        'views/endpoint_agent_views.xml',
        'views/endpoint_enrollment_key_views.xml',
        'views/hardware_views.xml',
        'views/remote_command_views.xml',
        'views/discovery_scan_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/endpoint_menus.xml',
        'wizard/endpoint_enrollment_key_reveal_views.xml',
    ],
    'installable': True,
    'application': False,
}
