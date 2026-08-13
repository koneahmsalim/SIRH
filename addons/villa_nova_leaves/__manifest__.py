{
    'name': "Villa Nova - Congés et Absences",
    'summary': "Politique de conges Villa Nova (accrual 2,5j/mois + paliers d'anciennete), "
               "conge maternite trace etape par etape, permissions exceptionnelles a duree "
               "auto-calculee, rappels conge maladie et absences non planifiees (delais legaux "
               "48h/24h/72h)",
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Time Off',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': [
        'villa_nova_recruitment',
        'villa_nova_onboarding',
        'hr_holidays',
        'hr_holidays_contract',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/leave_type_data.xml',
        'data/accrual_plan_data.xml',
        'data/cron_data.xml',
        'views/hr_leave_views.xml',
        'views/hr_maternity_process_views.xml',
        'views/hr_unplanned_absence_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
