from odoo import fields, models

from .itsm_ticket import TICKET_TYPE_SELECTION


class ItsmTicketTemplate(models.Model):
    """Modele de ticket pre-rempli (pour les demandes recurrentes creees
    directement par un agent, ex. "Nouvel arrivant"). Distinct du futur
    Service Catalog (Phase 8) qui portera un vrai workflow d'approbation :
    ici c'est un simple pre-remplissage, pas une demande formalisee."""
    _name = 'itsm.ticket.template'
    _description = "Modèle de ticket"
    _order = 'name'

    name = fields.Char(string="Nom", required=True)
    active = fields.Boolean(default=True)
    ticket_type = fields.Selection(TICKET_TYPE_SELECTION, string="Type", default='incident', required=True)
    subject = fields.Char(string="Sujet", required=True)
    description = fields.Html(string="Description")
    category_id = fields.Many2one('itsm.category', string="Catégorie")
    service_id = fields.Many2one('itsm.service', string="Service")
    team_id = fields.Many2one('itsm.team', string="Équipe")
    impact = fields.Selection([('low', "Faible"), ('medium', "Moyenne"), ('high', "Élevée")], string="Impact", default='medium')
    urgency = fields.Selection([('low', "Faible"), ('medium', "Moyenne"), ('high', "Élevée")], string="Urgence", default='medium')
    tag_ids = fields.Many2many('itsm.tag', string="Étiquettes")

    def action_create_ticket(self):
        self.ensure_one()
        ticket = self.env['itsm.ticket'].create({
            'ticket_type': self.ticket_type,
            'subject': self.subject,
            'description': self.description,
            'category_id': self.category_id.id,
            'service_id': self.service_id.id,
            'team_id': self.team_id.id,
            'impact': self.impact,
            'urgency': self.urgency,
            'tag_ids': [(6, 0, self.tag_ids.ids)],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'itsm.ticket',
            'res_id': ticket.id,
            'view_mode': 'form',
            'target': 'current',
        }
