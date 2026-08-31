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
    'data': [],
    'assets': {
        'web.assets_backend': [
            'villa_nova_project/static/src/scss/board.scss',
        ],
    },
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init',
}
