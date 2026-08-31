{
    'name': "Villa Nova - Gestion de projet",
    'summary': (
        "Habillage et fonctionnalites facon Asana pour la gestion de projet : "
        "tableaux, Mes taches, Portfolio multi-projets."
    ),
    'version': '18.0.1.0.0',
    'category': 'Services/Project',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['project', 'hr_timesheet', 'villa_nova_theme'],
    'data': [
        'views/project_task_list_view.xml',
        'views/my_tasks_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'villa_nova_project/static/src/scss/board.scss',
            'villa_nova_project/static/src/my_tasks/my_tasks.scss',
            'villa_nova_project/static/src/my_tasks/my_tasks.xml',
            'villa_nova_project/static/src/my_tasks/my_tasks.js',
        ],
    },
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init',
}
