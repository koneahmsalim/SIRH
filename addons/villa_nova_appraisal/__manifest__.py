{
    'name': "Villa Nova - Processus d'Evaluation",
    'summary': "Cycles d'evaluation (objectifs SMART/OKR, notation 60/40, circuits Manager et "
               "Collaborateur N-1, delais SLA) selon le processus d'evaluation et suivi de "
               "performance Villa Nova / Infinity Africa Group",
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Appraisals',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': [
        'villa_nova_recruitment',
        'villa_nova_onboarding',
        'hr_contract',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule_data.xml',
        'views/hr_appraisal_evaluation_views.xml',
        'views/hr_appraisal_cycle_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
