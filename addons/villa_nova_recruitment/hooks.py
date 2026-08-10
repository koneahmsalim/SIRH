def post_init_hook(env):
    """Ne pas repasser en brouillon les postes deja publies avant l'installation du module."""
    published_jobs = env['hr.job'].search([('is_published', '=', True)])
    published_jobs.write({'x_validation_state': 'validated'})
