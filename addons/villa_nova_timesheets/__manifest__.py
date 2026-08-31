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
    'depends': ['hr_timesheet', 'villa_nova_leaves', 'hr_attendance', 'villa_nova_theme'],
    'data': [
        'security/ir.model.access.csv',
        'security/default_user_groups.xml',
        'views/timesheet_activity_views.xml',
        'views/account_analytic_line_views.xml',
        'views/my_week_action.xml',
        'views/my_timesheets_week_action.xml',
        'views/all_timesheets_week_action.xml',
        'data/villa.nova.timesheet.activity.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'villa_nova_timesheets/static/src/my_week/my_week.scss',
            'villa_nova_timesheets/static/src/my_week/my_week.xml',
            'villa_nova_timesheets/static/src/my_week/my_week.js',
            'villa_nova_timesheets/static/src/my_timesheets_week/my_timesheets_week.scss',
            'villa_nova_timesheets/static/src/my_timesheets_week/my_timesheets_week.xml',
            'villa_nova_timesheets/static/src/my_timesheets_week/my_timesheets_week.js',
        ],
    },
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init',
}
