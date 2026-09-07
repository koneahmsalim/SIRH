{
    'name': "Villa Nova - Base de connaissances & Catalogue de services",
    'summary': (
        "Base de connaissances (articles publies/brouillons, suggestions "
        "automatiques sur les tickets par categorie, retours utile/pas "
        "utile) et catalogue de services navigable sur le portail "
        "self-service - relies aux tickets et services existants. Integre "
        "dans l'app ITSM unifiee. Phase 8 de la plateforme ITSM complete "
        "construite phase par phase."
    ),
    'version': '18.0.1.0.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['villa_nova_itsm', 'website'],
    'data': [
        'security/knowledge_security.xml',
        'security/ir.model.access.csv',
        'views/itsm_kb_article_views.xml',
        'views/itsm_ticket_kb_views.xml',
        'views/knowledge_menus.xml',
        'views/portal_templates.xml',
    ],
    'demo': [
        'demo/knowledge_demo.xml',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init',
}
