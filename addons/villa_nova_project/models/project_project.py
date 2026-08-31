from odoo import api, fields, models

OVERDUE_RATIO_LATE = 0.3
RISK_DEADLINE_DAYS = 14
RISK_PROGRESS_THRESHOLD = 70


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.model
    def get_portfolio_data(self):
        """Sante calculee automatiquement a partir des vraies taches
        (retard, echeance proche) plutot que le statut "last_update_status"
        natif, qui exige qu'un chef de projet le saisisse manuellement -
        personne ne le fait ici, les 11 projets restent sur leur valeur par
        defaut. Equivalent des Portfolios Asana, en automatique."""
        projects = self.search([('active', '=', True)])
        today = fields.Date.context_today(self)
        Task = self.env['project.task']
        result = []
        for project in projects:
            tasks = Task.search([('project_id', '=', project.id)])
            open_tasks = tasks.filtered(lambda t: t.state not in ('1_done', '1_canceled'))
            done_count = len(tasks.filtered(lambda t: t.state == '1_done'))
            total_for_progress = len(tasks) - len(tasks.filtered(lambda t: t.state == '1_canceled'))
            progress = round(done_count / total_for_progress * 100) if total_for_progress else 0

            dated_open = open_tasks.filtered(lambda t: t.date_deadline)
            overdue = dated_open.filtered(lambda t: t.date_deadline.date() < today)
            overdue_ratio = len(overdue) / len(dated_open) if dated_open else 0

            deadline_soon = bool(
                project.date and 0 <= (project.date - today).days <= RISK_DEADLINE_DAYS and progress < 100
            )
            deadline_passed = bool(project.date and project.date < today and progress < 100)

            if not tasks:
                # Aucune tache suivie : une echeance de projet depassee ne
                # veut rien dire ici (rien n'a ete commence ou trace), pas
                # la peine d'afficher "En retard" sur du vide.
                health = 'no_data'
            elif overdue_ratio >= OVERDUE_RATIO_LATE or deadline_passed:
                health = 'late'
            elif overdue_ratio > 0 or (deadline_soon and progress < RISK_PROGRESS_THRESHOLD):
                health = 'at_risk'
            else:
                health = 'on_track'

            team = open_tasks.mapped('user_ids')
            result.append({
                'id': project.id,
                'name': project.name,
                'color': project.color,
                'manager': {'id': project.user_id.id, 'name': project.user_id.name} if project.user_id else None,
                'date': project.date and fields.Date.to_string(project.date),
                'progress': progress,
                'task_count': len(tasks),
                'open_task_count': len(open_tasks),
                'overdue_count': len(overdue),
                'health': health,
                'team': [{'id': u.id, 'name': u.name} for u in team],
            })
        return result
