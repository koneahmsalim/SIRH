CATEGORY_TO_DEPARTMENTS = {
    "Bureau du Président": ["Bureau du Président"],
    "Finance et contrôle de gestion": ["Finance & Comptabilité"],
    "Comptabilité": ["Finance & Comptabilité"],
    "Ressources humaines": ["Ressources Humaines"],
    "Communication": ["Communication"],
    "Administration": ["Administration"],
    "IAT Solutions": ["Technologie", "Recherche & Développement", "R&D USA", "Projets à long terme"],
    "IAT Consulting": ["Services professionnels"],
    # Pas de departement Villa Nova correspondant actuellement : ces codes
    # restent importes (reference complete du groupe) mais invisibles tant
    # qu'aucun employe n'est rattache a un departement pour ces entites.
    "Contrôle, audit et conformité": [],
    "Support IT": [],
    "Juridique et conformité": [],
    "Banque d'affaires": [],
    "Financement PME": [],
    "Venture Capital": [],
    "Immobilier": [],
    "Marchés financiers": [],
}


def link_activity_departments(env):
    Department = env['hr.department']
    Activity = env['villa.nova.timesheet.activity']
    for category, dept_names in CATEGORY_TO_DEPARTMENTS.items():
        if not dept_names:
            continue
        departments = Department.search([('name', 'in', dept_names)])
        activities = Activity.search([
            ('category_lvl1', '=', category),
            ('visibility_scope', '=', 'department'),
        ])
        if departments and activities:
            activities.write({'department_ids': [(6, 0, departments.ids)]})
