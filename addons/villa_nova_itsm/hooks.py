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


def post_init(env):
    seed_automation_rules(env)
