{
    'name': "Villa Nova - Présences biométriques (déduction entrée/sortie)",
    'summary': (
        "Le boitier ZK F18 envoie tous les pointages avec un code generique (255) "
        "au lieu de 0 (entree) / 1 (sortie) attendu par hr_biometric_attendance. "
        "Ce module deduit entree/sortie (premier/dernier pointage du jour) et "
        "synchronise automatiquement les nouveaux pointages toutes les 15 minutes "
        "(le boitier n'a pas d'API de lecture incrementale : chaque pull renvoie "
        "tout l'historique, d'ou un intervalle prudent)."
    ),
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['hr_biometric_attendance'],
    'data': [
        'views/biometric_device_details_views.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
}
