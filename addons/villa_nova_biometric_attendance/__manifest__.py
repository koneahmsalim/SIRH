{
    'name': "Villa Nova - Présences biométriques (déduction entrée/sortie)",
    'summary': (
        "Le boitier ZK F18 envoie tous les pointages avec un code generique (255) "
        "au lieu de 0 (entree) / 1 (sortie) attendu par hr_biometric_attendance. "
        "Ce module deduit entree/sortie (premier/dernier pointage du jour), etiquette "
        "chaque pointage 'Boitier biometrique' (in_mode/out_mode natifs, pour le "
        "distinguer d'un pointage via le bouton libre-service ou d'une saisie RH) et "
        "synchronise automatiquement les nouveaux pointages toutes les 3 minutes "
        "(le boitier n'a pas d'API de lecture incrementale : chaque pull renvoie "
        "tout l'historique, mesure a ~11s pour ~1200 pointages, marge large)."
    ),
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['hr_attendance', 'hr_biometric_attendance', 'hr_holidays'],
    'data': [
        'security/ir.model.access.csv',
        'views/biometric_device_details_views.xml',
        'views/hr_attendance_views.xml',
        'views/attendance_report_wizard_views.xml',
        'report/attendance_report_actions.xml',
        'report/attendance_report_templates.xml',
        'data/ir_cron_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'villa_nova_biometric_attendance/static/src/attendance_menu_patch.js',
        ],
    },
    'installable': True,
    'application': False,
}
