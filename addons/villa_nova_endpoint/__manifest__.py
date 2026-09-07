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
        "arbitraire), envoi en un clic via un assistant depuis la fiche de "
        "l'actif, et audit complet par commande. Decouverte reseau (scan "
        "ping sweep nmap a la demande, rapprochement best-effort avec les "
        "actifs deja connus). Bibliotheque de scripts approuves (empreinte "
        "SHA-256 figee a la soumission - executable uniquement via une "
        "commande a distance, elle-meme soumise a approbation). Phases 2-5 "
        "et 7-8 (Agent MVP, Console de gestion, Actions a distance, "
        "Decouverte reseau, Gestion de scripts, Controle a distance via "
        "MeshCentral auto-heberge - Odoo stocke juste l'identifiant du poste "
        "et genere le lien, aucune prise de main reimplementee ici) et 9 "
        "(triage de risque du parc : detection d'OS en fin de support + "
        "signaux de conformite deja remontes - PAS un scanner de "
        "vulnerabilites CVE, perimetre hors de portee) de la plateforme "
        "Endpoint Management/RMM construite phase par phase, apres les 12 "
        "phases ITSM. Phase 6 (Active Directory) explicitement en attente."
    ),

    'icon': '/villa_nova_endpoint/static/description/icon.png',

    'version': '18.0.1.6.0',
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
        'views/approved_script_views.xml',
        'views/remote_command_views.xml',
        'views/discovery_scan_views.xml',
        'views/security_risk_views.xml',
        'wizard/endpoint_enrollment_key_reveal_views.xml',
        'wizard/remote_command_wizard_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/res_config_settings_views.xml',
        'views/endpoint_menus.xml',
    ],
    'installable': True,
    'application': False,
}
