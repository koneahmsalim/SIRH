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


NOTIFY_CREATOR_NAME = "Villa Nova - Tâche terminée : notifier le créateur"
OVERDUE_REMINDER_NAME = "Villa Nova - Échéance dépassée : relancer l'assigné"


def _create_notify_creator_rule(env, model):
    """Regle "on_state_set" (mecanisme natif base.automation, aucun code de
    detection de transition a maintenir soi-meme) : notifie l'auteur de la
    tache des qu'elle passe a Fait - equivalent des Rules Asana les plus
    utilisees. Le champ filter_domain/trigger_field_ids se deduit tout seul
    du trigger, il ne faut pas les fixer a la main (ce sont des champs
    calcules)."""
    state_field = env['ir.model.fields'].search(
        [('model', '=', 'project.task'), ('name', '=', 'state')], limit=1)
    done_selection = env['ir.model.fields.selection'].search(
        [('field_id', '=', state_field.id), ('value', '=', '1_done')], limit=1)
    if not done_selection:
        return

    rule = env['base.automation'].create({
        'name': NOTIFY_CREATOR_NAME,
        'model_id': model.id,
        'trigger': 'on_state_set',
        'trg_selection_field_id': done_selection.id,
    })
    env['ir.actions.server'].create({
        'name': NOTIFY_CREATOR_NAME + " (action)",
        'base_automation_id': rule.id,
        'model_id': model.id,
        'state': 'code',
        'code': (
            "if record.create_uid and record.create_uid.partner_id:\n"
            "    record.message_post(\n"
            "        body=\"La tâche « %s » est passée à Fait.\" % record.name,\n"
            "        partner_ids=[record.create_uid.partner_id.id],\n"
            "    )\n"
        ),
    })


def _create_overdue_reminder_rule(env, model):
    """Regle "on_time" (2 jours apres l'echeance) : programme un rappel pour
    l'assigne si la tache n'est ni terminee ni annulee et n'a pas deja une
    activite en cours (evite les doublons de relance)."""
    deadline_field = env['ir.model.fields'].search(
        [('model', '=', 'project.task'), ('name', '=', 'date_deadline')], limit=1)
    if not deadline_field:
        return

    rule = env['base.automation'].create({
        'name': OVERDUE_REMINDER_NAME,
        'model_id': model.id,
        'trigger': 'on_time',
        'trg_date_id': deadline_field.id,
        'trg_date_range': 2,
        'trg_date_range_type': 'day',
        'filter_domain': "[('state', 'not in', ['1_done', '1_canceled'])]",
    })
    env['ir.actions.server'].create({
        'name': OVERDUE_REMINDER_NAME + " (action)",
        'base_automation_id': rule.id,
        'model_id': model.id,
        'state': 'code',
        'code': (
            "if not record.activity_ids:\n"
            "    for assignee in record.user_ids:\n"
            "        record.activity_schedule(\n"
            "            'mail.mail_activity_data_todo',\n"
            "            summary=\"Échéance dépassée : %s\" % record.name,\n"
            "            note=\"Cette tâche est en retard depuis plusieurs jours et n'a pas encore été marquée terminée.\",\n"
            "            user_id=assignee.id,\n"
            "        )\n"
        ),
    })


def seed_automation_rules(env):
    if env['base.automation'].search_count([('name', 'in', [NOTIFY_CREATOR_NAME, OVERDUE_REMINDER_NAME])]):
        return
    model = env.ref('project.model_project_task')
    _create_notify_creator_rule(env, model)
    _create_overdue_reminder_rule(env, model)


def post_init(env):
    backfill_missing_stages(env)
    seed_example_task_properties(env)
    seed_automation_rules(env)
