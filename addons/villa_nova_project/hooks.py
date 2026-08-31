def backfill_missing_stages(env):
    """Certains projets reels (ex. AfriScore) n'ont aucun stade Kanban
    configure (type_ids vide) : le tableau ne peut rien afficher. On leur
    donne le jeu de stades canonique deja partage par les autres projets
    actifs (Nouveau / En cours / Termine / Annule - stades de base Odoo),
    plutot que d'en creer un nouveau qui dupliquerait encore la liste."""
    canonical_xmlids = [
        'project.project_stage_0',
        'project.project_stage_1',
        'project.project_stage_2',
        'project.project_stage_3',
    ]
    stages = env['project.task.type'].browse([
        env.ref(xmlid).id for xmlid in canonical_xmlids
        if env.ref(xmlid, raise_if_not_found=False)
    ])
    if not stages:
        return
    projects = env['project.project'].search([('type_ids', '=', False)])
    if projects:
        projects.write({'type_ids': [(6, 0, stages.ids)]})


PRIORITE_BUSINESS_SELECTION = [
    ['faible', "Faible"],
    ['moyenne', "Moyenne"],
    ['elevee', "Élevée"],
    ['critique', "Critique"],
]

ENTITE_IAG_SELECTION = [
    ['iat_solutions', "IAT Solutions"],
    ['iat_consulting', "IAT Consulting"],
    ['capital', "Infinity Africa Capital"],
    ['finance', "Infinity Africa Finance"],
    ['ventures', "Infinity Africa Ventures"],
    ['properties', "Infinity Africa Properties"],
    ['securities', "Infinity Africa Securities"],
    ['technologies', "Infinity Africa Technologies"],
]


def seed_example_task_properties(env):
    """Gabarit de "Proprietes personnalisees" (task_properties_definition,
    fonctionnalite native Odoo 18 Community - equivalent direct des Custom
    Fields Asana) applique a un projet reel a titre d'exemple, pas a tous
    les projets : une equipe l'active elle-meme sur ses projets via
    Parametres du projet > Proprietes des taches, en copiant ce modele.
    "Priorite business" comble un vrai manque natif (le champ priority
    d'Odoo Community n'est qu'une etoile binaire, pas une echelle)."""
    project = env['project.project'].search([('name', '=', 'Office Design')], limit=1)
    if not project or project.task_properties_definition:
        return
    project.task_properties_definition = [
        {
            'name': 'villa_nova_priorite_business',
            'string': "Priorité business",
            'type': 'selection',
            'selection': PRIORITE_BUSINESS_SELECTION,
        },
        {
            'name': 'villa_nova_entite_iag',
            'string': "Entité IAG",
            'type': 'selection',
            'selection': ENTITE_IAG_SELECTION,
        },
    ]


def post_init(env):
    backfill_missing_stages(env)
    seed_example_task_properties(env)
