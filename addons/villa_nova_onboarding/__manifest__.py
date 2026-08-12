{
    'name': "Villa Nova - Processus d'Onboarding",
    'summary': "Automatise la checklist pre-onboarding, les emails d'integration, le suivi du parrain "
               "et l'enquete de satisfaction J+30, selon l'annexe onboarding Villa Nova / Infinity Africa Group",
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Employees',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': [
        'villa_nova_recruitment',
        'hr',
        'hr_contract',
        'survey',
        'calendar',
    ],
    'data': [
        'security/security.xml',
        'data/survey_satisfaction_j30_data.xml',
        'data/mail_templates_data.xml',
        'data/cron_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_onboarding_dashboard_views.xml',
    ],
    'installable': True,
    'application': False,
}
