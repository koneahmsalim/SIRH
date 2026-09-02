import logging

_logger = logging.getLogger(__name__)

# Les groupes natifs eLearning (Fonctionnaire = createur/editeur de cours,
# Manager = idem + suppression) contenaient 59 membres a l'installation de
# ce module - la quasi-totalite du personnel, y compris des postes sans
# aucun rapport avec la formation. Cause probable : seed/demo data qui
# accorde ces droits par defaut. Restreint au departement Ressources
# Humaines, le seul habilite a piloter le contenu de formation - demande
# explicite utilisateur ("il faut creer un droit pour pouvoir ajouter un
# cours").
HR_DEPARTMENT_NAME = "Ressources Humaines"


def restrict_course_management_to_hr(env):
    officer = env.ref('website_slides.group_website_slides_officer', raise_if_not_found=False)
    manager = env.ref('website_slides.group_website_slides_manager', raise_if_not_found=False)
    if not officer or not manager:
        return

    hr_department = env['hr.department'].search([('name', '=', HR_DEPARTMENT_NAME)], limit=1)
    hr_users = hr_department.mapped('member_ids.user_id') if hr_department else env['res.users']

    officer.write({'users': [(6, 0, hr_users.ids)]})
    manager.write({'users': [(6, 0, [])]})
    _logger.info(
        "villa_nova_elearning: droits de gestion des cours restreints a %s (%d utilisateur(s))",
        HR_DEPARTMENT_NAME, len(hr_users),
    )


def post_init(env):
    restrict_course_management_to_hr(env)
