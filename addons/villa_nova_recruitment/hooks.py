def post_init_hook(env):
    """Ne pas repasser en brouillon les postes deja publies avant l'installation du module,
    et brancher le test de prequalification par defaut sur les postes qui n'en ont pas."""
    published_jobs = env['hr.job'].search([('is_published', '=', True)])
    published_jobs.write({'x_validation_state': 'validated'})

    survey = env.ref('villa_nova_recruitment.survey_prequalification', raise_if_not_found=False)
    if survey:
        jobs_without_survey = env['hr.job'].search([('survey_id', '=', False)])
        jobs_without_survey.write({'survey_id': survey.id})
