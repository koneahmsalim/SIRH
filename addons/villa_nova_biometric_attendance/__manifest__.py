{
    'name': "Villa Nova - Présences biométriques (déduction entrée/sortie)",
    'summary': (
        "Le boitier ZK F18 envoie tous les pointages avec un code generique (255) "
        "au lieu de 0 (entree) / 1 (sortie) attendu par hr_biometric_attendance. "
        "Ce module deduit entree/sortie par alternance quand le code est absent."
    ),
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': ['hr_biometric_attendance'],
    'data': [],
    'installable': True,
    'application': False,
}
