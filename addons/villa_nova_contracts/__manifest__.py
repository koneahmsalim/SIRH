{
    'name': "Villa Nova - Contrats, garanties & fournisseurs",
    'summary': (
        "Contrats de support/maintenance/licence (dates, cout, actifs et "
        "licences couverts), tracabilite achat via les bons de commande "
        "natifs (module purchase, deja installe), visibilite fournisseur "
        "sur la fiche contact (actifs fournis, contrats), rappels de "
        "renouvellement (contrats, garanties materielles, licences) par "
        "activite planifiee. Demande d'achat -> approbation -> bon de "
        "commande (genere directement un vrai purchase.order natif) - gap "
        "identifie par rapport a ServiceDesk Plus, reutilise le moteur "
        "d'approbation existant. Integre dans l'app ITSM unifiee. Phase 11 "
        "de la plateforme ITSM complete construite phase par phase."
    ),
    'version': '18.0.1.1.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['villa_nova_itam', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/ir_sequence_data.xml',
        'views/itsm_contract_views.xml',
        'views/itam_equipment_contract_views.xml',
        'views/res_partner_vendor_views.xml',
        'views/itam_purchase_request_views.xml',
        'views/contract_menus.xml',
    ],
    'demo': [
        'demo/contracts_demo.xml',
    ],
    'installable': True,
    'application': False,
}
