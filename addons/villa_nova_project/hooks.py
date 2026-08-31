def post_init(env):
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
