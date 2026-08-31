CATEGORY_TO_DEPARTMENTS = {
    "Bureau du Président": ["Bureau du Président"],
    "Finance et contrôle de gestion": ["Finance & Comptabilité"],
    "Comptabilité": ["Finance & Comptabilité"],
    "Ressources humaines": ["Ressources Humaines"],
    "Communication": ["Communication"],
    "Administration": ["Administration"],
    "IAT Solutions": ["Technologie", "Recherche & Développement", "R&D USA", "Projets à long terme"],
    "IAT Consulting": ["Services professionnels"],
    "Banque d'affaires": ["Infinity Africa Capital"],
    "Financement PME": ["Infinity Africa Finance"],
    "Venture Capital": ["Infinity Africa Ventures"],
    "Immobilier": ["Infinity Africa Properties"],
    "Marchés financiers": ["Infinity Africa Securities"],
    # Pas de departement Villa Nova correspondant actuellement : ces codes
    # restent importes (reference complete du groupe) mais invisibles tant
    # qu'aucun employe n'est rattache a un departement pour ces entites.
    "Contrôle, audit et conformité": [],
    "Support IT": [],
    "Juridique et conformité": [],
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


def grant_timesheet_access_to_employees(env):
    """Sans ce groupe, un employe ne peut creer aucune ligne de feuille de
    temps (ni via 'Ma semaine' ni via la grille standard) - seuls les comptes
    admin/DRH l'avaient. Rattrapage pour les comptes existants ; les nouveaux
    comptes l'obtiennent via le modele base.default_user (security XML)."""
    group = env.ref('hr_timesheet.group_hr_timesheet_user', raise_if_not_found=False)
    internal = env.ref('base.group_user', raise_if_not_found=False)
    if not group or not internal:
        return
    employees = env['hr.employee'].search([('user_id', '!=', False)])
    users = employees.mapped('user_id').filtered(
        lambda u: internal in u.groups_id and group not in u.groups_id
    )
    if users:
        users.write({'groups_id': [(4, group.id)]})


def post_init(env):
    link_activity_departments(env)
    grant_timesheet_access_to_employees(env)
