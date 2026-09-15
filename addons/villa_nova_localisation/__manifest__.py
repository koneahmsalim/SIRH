{
    'name': "Villa Nova - Localisation Côte d'Ivoire",
    'summary': "Adaptation locale du SIRH : libellés en français pour les modules RH tiers "
               "restés en anglais, types de contrat, préavis et couverture sociale conformes "
               "au droit du travail ivoirien (CNPS, CMU, Convention Collective "
               "Interprofessionnelle)",
    'description': """
Deux volets, indissociables dans une mise en service locale :

1. Langue — les modules RH tiers (OpenHRMS et assimilés) livrent leur interface en
   anglais. Les libellés sont repris ici en équivalents métier français, pas en
   traduction mot à mot : "Transfers" devient "Mutations", "Appraisal" devient
   "Entretiens d'évaluation", "Resignation" devient "Départs" (le modèle couvre la
   démission comme le licenciement).

2. Droit ivoirien — types de contrat, barème de préavis de la Convention Collective
   Interprofessionnelle (art. 34) et régimes de couverture sociale obligatoires
   (CNPS, CMU).
""",
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Localization',
    'author': 'Villa Nova',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_contract',
        'hr_payroll_community',
        'hr_insurance',
        'hr_resignation',
        'hr_reminder',
        'hr_employee_transfer',
        'hr_reward_warning',
        'oh_appraisal',
        'oh_employee_documents_expiry',
        'ohrms_loan',
        'ohrms_salary_advance',
        'ohrms_service_request',
        'hr_biometric_attendance',
        'hrms_dashboard',
        'hr_gamification',
        'hr_employee_updation',
    ],
    'data': [
        'data/menus_fr_data.xml',
        'data/hr_contract_type_data.xml',
        'data/insurance_policy_data.xml',
        'views/hr_resignation_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_insurance_views.xml',
    ],
    'installable': True,
    'application': False,
}
