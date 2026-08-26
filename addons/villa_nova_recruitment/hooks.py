def post_init_hook(env):
    """Ne pas repasser en brouillon les postes deja publies avant l'installation du module,
    et brancher le test de prequalification par defaut sur les postes qui n'en ont pas."""
    published_jobs = env['hr.job'].search([('is_published', '=', True)])
    published_jobs.write({'x_validation_state': 'validated'})

    survey = env.ref('villa_nova_recruitment.survey_prequalification', raise_if_not_found=False)
    if survey:
        jobs_without_survey = env['hr.job'].search([('survey_id', '=', False)])
        jobs_without_survey.write({'survey_id': survey.id})

    _enable_candidate_signup(env)


def _enable_candidate_signup(env):
    """Ce module rend le compte candidat obligatoire pour postuler (voir
    controllers/main.py, /jobs/apply redirige vers /web/login) - mais par
    defaut, Odoo n'affiche le lien "Creer un compte" sur /web/login que si
    l'inscription libre est activee. Sans ce reglage, un visiteur externe
    tombe sur un simple ecran de connexion sans issue (aucun moyen de creer
    le compte que ce module exige) - bug reel constate et corrige en
    production le 18/08, jusque-la seulement en base (jamais persiste dans
    le code, donc reproduit a l'identique sur toute nouvelle installation).
    Deux reglages distincts controlent ce comportement selon le contexte
    (backend vs site web, cf. auth_signup/controllers/main.py et
    website/models/res_users.py::_get_signup_invitation_scope) : les deux
    doivent etre actives.
    """
    env['ir.config_parameter'].sudo().set_param('auth_signup.invitation_scope', 'b2c')
    env['website'].sudo().search([]).write({'auth_signup_uninvited': 'b2c'})
