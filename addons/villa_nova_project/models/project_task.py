from odoo import models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

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
