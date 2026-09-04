{
    'name': "Villa Nova - ITSM (Service Desk)",
    'summary': (
        "Service Desk natif Odoo Community (pas de dependance a l'Helpdesk "
        "Enterprise) : tickets (incidents/demandes/questions/reclamations), "
        "equipes, categories, SLA avec calcul sur calendrier ouvre, escalade, "
        "portail, tableau de bord agent. Fondation d'une plateforme ITSM "
        "complete construite phase par phase (SLA avance, ITAM, CMDB, "
        "Problem/Change/Release, Knowledge, Portail avance, Analytics, "
        "Contrats/Fournisseurs, API - a venir dans des phases ulterieures)."
    ),
    'version': '18.0.1.0.0',
    'category': 'Services/Helpdesk',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['mail', 'portal', 'resource', 'hr', 'base_automation', 'villa_nova_theme'],
    'data': [
        'security/itsm_security.xml',
        'security/ir.model.access.csv',
        'security/itsm_security_rules.xml',
        'security/automation_rules_security.xml',
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        'data/itsm_cron_data.xml',
        'views/itsm_ticket_views.xml',
        'views/itsm_team_views.xml',
        'views/itsm_category_views.xml',
        'views/itsm_service_views.xml',
        'views/itsm_sla_policy_views.xml',
        'views/itsm_tag_views.xml',
        'views/itsm_ticket_template_views.xml',
        'views/itsm_canned_response_views.xml',
        'views/itsm_approval_views.xml',
        'views/portal_templates.xml',
        'views/itsm_menus.xml',
        'views/automation_rules_view.xml',
    ],
    'demo': [
        'demo/itsm_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'villa_nova_itsm/static/src/dashboard/dashboard.scss',
            'villa_nova_itsm/static/src/dashboard/dashboard.xml',
            'villa_nova_itsm/static/src/dashboard/dashboard.js',
            'villa_nova_itsm/static/src/ticket_kanban/ticket_kanban.scss',
        ],
    },
    'installable': True,
    'application': True,
    'post_init_hook': 'post_init',
}
