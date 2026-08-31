from odoo import api, fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Odoo Community n'a pas de champ de debut planifie sur les taches
    # (date_end = date de cloture reelle, pas une date prevue) - necessaire
    # pour tracer une barre dans la Timeline (villa_nova_project), pas
    # seulement un point d'echeance.
    date_start = fields.Datetime(
        string="Début planifié",
        help="Date de début prévue de la tâche, utilisée par la vue Timeline.",
    )

    @api.model
    def get_timeline_data(self, date_from, date_to):
        """Taches ayant une des deux dates (debut planifie ou echeance) et
        dont l'intervalle [debut, echeance] chevauche la fenetre visible.
        Sans date_start, l'echeance sert aussi de debut (barre d'un jour) -
        et inversement."""
        window_start = fields.Datetime.from_string(date_from)
        window_end = fields.Datetime.from_string(date_to)
        tasks = self.search([
            ('project_id', '!=', False),
            '|', ('date_start', '!=', False), ('date_deadline', '!=', False),
        ], order='project_id, date_start, date_deadline')

        result = []
        for task in tasks:
            start = task.date_start or task.date_deadline
            end = task.date_deadline or task.date_start
            if end < window_start or start > window_end:
                continue
            result.append({
                'id': task.id,
                'name': task.name,
                'project_id': task.project_id.id,
                'project_name': task.project_id.name,
                'date_start': fields.Datetime.to_string(start),
                'date_deadline': fields.Datetime.to_string(end),
                'state': task.state,
                'depend_on_ids': task.depend_on_ids.ids,
            })
        return result

    @api.model
    def get_workload_data(self, date_from, date_to):
        """Une ligne par (tache, assigne) avec ses dates - la repartition
        heures/jour et l'agregation par utilisateur se font cote client
        (comme pour la Timeline), pour ne faire qu'un seul appel serveur."""
        window_start = fields.Datetime.from_string(date_from)
        window_end = fields.Datetime.from_string(date_to)
        tasks = self.search([
            ('user_ids', '!=', False),
            ('state', 'not in', ['1_done', '1_canceled']),
            '|', ('date_start', '!=', False), ('date_deadline', '!=', False),
        ])

        result = []
        for task in tasks:
            start = task.date_start or task.date_deadline
            end = task.date_deadline or task.date_start
            if end < window_start or start > window_end:
                continue
            span_days = (end.date() - start.date()).days + 1
            hours_per_day = (task.allocated_hours or 0) / span_days if span_days else 0
            for user in task.user_ids:
                result.append({
                    'user_id': user.id,
                    'user_name': user.name,
                    'task_id': task.id,
                    'task_name': task.name,
                    'date_start': fields.Datetime.to_string(start),
                    'date_deadline': fields.Datetime.to_string(end),
                    'hours_per_day': hours_per_day,
                })
        return result

    def action_villa_nova_view_depend_on(self):
        """"Bloque par" (depend_on_ids) n'a nativement qu'un onglet dans le
        formulaire, pas de bouton statistique contrairement a "Bloque"
        (action_dependent_tasks juste a cote) - meme pattern, cote symetrique."""
        self.ensure_one()
        return {
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'context': {**self._context, 'search_default_open_tasks': True},
            'domain': [('id', 'in', self.depend_on_ids.ids)],
            'name': _('Bloqué par'),
            'view_mode': 'list,form,kanban,calendar,pivot,graph,activity',
        }
