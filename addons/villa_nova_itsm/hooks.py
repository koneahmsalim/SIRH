NOTIFY_CRITICAL_NAME = "ITSM - Ticket critique : notifier le responsable d'équipe"


def _create_notify_critical_rule(env):
    """Regle d'automatisation native (base.automation, mecanisme 100%
    Community) : quand un ticket passe en priorite critique, le responsable
    de l'equipe recoit une activite a traiter. Cree une seule fois (verifie
    par nom) - modifiable/desactivable ensuite depuis l'interface par un
    administrateur ITSM (voir automation_rules_view.xml pour l'acces
    restreint mais reel accorde aux managers ITSM)."""
    if env['base.automation'].search([('name', '=', NOTIFY_CRITICAL_NAME)]):
        return

    model = env['ir.model'].search([('model', '=', 'itsm.ticket')], limit=1)
    if not model:
        return
    priority_field = env['ir.model.fields'].search([
        ('model_id', '=', model.id), ('name', '=', 'priority'),
    ], limit=1)
    if not priority_field:
        return
    critical_selection = env['ir.model.fields.selection'].search([
        ('field_id', '=', priority_field.id), ('value', '=', 'critical'),
    ], limit=1)
    if not critical_selection:
        return

    automation = env['base.automation'].create({
        'name': NOTIFY_CRITICAL_NAME,
        'model_id': model.id,
        'trigger': 'on_priority_set',
        'trg_selection_field_id': critical_selection.id,
    })
    env['ir.actions.server'].create({
        'name': NOTIFY_CRITICAL_NAME,
        'base_automation_id': automation.id,
        'model_id': model.id,
        'state': 'code',
        'code': "record.action_automation_notify_critical()",
    })


def seed_automation_rules(env):
    _create_notify_critical_rule(env)


# Employes dont le poste correspond reellement a un role IT (departement
# Technologie + support IT en Administration) - rattaches aux equipes ITSM
# de demo pour permettre une demonstration et des tests de permissions
# multi-agents realistes (les equipes de demo Phase 1 n'avaient qu'un
# responsable, aucun membre).
TEAM_AGENT_LOGINS = {
    'villa_nova_itsm.demo_team_n1': [
        'badou@infinity-africa.com',
        'abdoulaye.meite@infinity-africa.com',
    ],
    'villa_nova_itsm.demo_team_n2': [
        'mederic.gbagba@infinity-africa.com',
        'fadel.koloma@infinity-africa.com',
    ],
    'villa_nova_itsm.demo_team_infra': [
        'elishama.brou@infinity-africa.com',
    ],
}


def _seed_demo_team_members(env):
    agent_group = env.ref('villa_nova_itsm.group_itsm_agent', raise_if_not_found=False)
    if not agent_group:
        return
    for team_xmlid, logins in TEAM_AGENT_LOGINS.items():
        team = env.ref(team_xmlid, raise_if_not_found=False)
        if not team:
            continue
        users = env['res.users'].search([('login', 'in', logins)])
        if not users:
            continue
        users.write({'groups_id': [(4, agent_group.id)]})
        team.write({'member_ids': [(4, user.id) for user in users]})


def post_init(env):
    seed_automation_rules(env)
    _seed_demo_team_members(env)
