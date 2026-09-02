{
    'name': "Villa Nova - eLearning",
    'summary': (
        "Habillage facon Asana pour la formation en ligne (website_slides) : "
        "vue 'Mes formations' avec progression, sans toucher aux vues natives."
    ),
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['website_slides', 'villa_nova_theme'],
    'data': [
        'views/my_trainings_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'villa_nova_elearning/static/src/my_trainings/my_trainings.scss',
            'villa_nova_elearning/static/src/my_trainings/my_trainings.xml',
            'villa_nova_elearning/static/src/my_trainings/my_trainings.js',
        ],
    },
    'installable': True,
    'application': False,
}
