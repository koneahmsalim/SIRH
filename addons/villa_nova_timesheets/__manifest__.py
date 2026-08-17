{
    'name': "Villa Nova - Feuilles de temps (nomenclature IAG)",
    'summary': (
        "Code activite obligatoire sur chaque ligne de feuille de temps, selon la "
        "nomenclature IAG du 5 aout 2026 : facturabilite par defaut, obligation de "
        "projet, visibilite par departement, alerte heures vs presence."
    ),
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Timesheets',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['hr_timesheet', 'villa_nova_leaves', 'hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'views/timesheet_activity_views.xml',
        'views/account_analytic_line_views.xml',
        'data/villa.nova.timesheet.activity.csv',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'link_activity_departments',
}
