from odoo import _, fields, models
from odoo.exceptions import UserError


class VillaNovaAssignTrainingWizard(models.TransientModel):
    _name = 'villa.nova.elearning.assign.wizard'
    _description = "Assigner une formation obligatoire"

    course_id = fields.Many2one('slide.channel', string="Formation", required=True)
    employee_ids = fields.Many2many('hr.employee', string="Employés", required=True)
    due_date = fields.Date(string="Échéance")

    def action_assign(self):
        self.ensure_one()
        partners = self.employee_ids.mapped('user_id.partner_id')
        if not partners:
            raise UserError(_("Aucun des employés sélectionnés n'a de compte utilisateur - "
                               "impossible de les inscrire à la formation."))

        # Reutilise le mecanisme natif d'inscription (abonnement au chatter,
        # gestion des reinscriptions/desarchivage) plutot que de creer les
        # lignes a la main. Attention : _action_add_members ne renvoie PAS
        # les employes deja inscrits et deja au statut "joined" (seulement
        # les nouveaux/reactives/passes d'invite a joined) - un employe
        # inscrit de son propre chef avant l'assignation obligatoire
        # tomberait donc dans un recordset vide et ne recevrait jamais le
        # marquage obligatoire. On recherche donc explicitement l'ensemble
        # complet apres coup plutot que de se fier a la valeur de retour.
        self.course_id._action_add_members(partners, member_status='joined')
        enrollments = self.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', self.course_id.id),
            ('partner_id', 'in', partners.ids),
        ])
        enrollments.write({
            'villa_nova_mandatory': True,
            'villa_nova_assigned_by': self.env.user.id,
            'villa_nova_due_date': self.due_date,
        })
        return {'type': 'ir.actions.act_window_close'}
