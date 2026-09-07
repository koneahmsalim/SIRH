{
    'name': "Villa Nova - Portail avancé ITSM",
    'summary': (
        "Portail self-service enrichi : pieces jointes sur creation de "
        "ticket et messages de suivi, visibilite SLA (echeance, statut) "
        "cote client, articles de la base de connaissances suggeres sur "
        "le ticket et lors de la creation d'une demande. Phase 9 de la "
        "plateforme ITSM complete construite phase par phase."
    ),
    'version': '18.0.1.0.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['villa_nova_knowledge'],
    'data': [
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}
