from odoo import fields, models


class ItsmService(models.Model):
    """Entree de Service Catalog minimale pour la Phase 1 (formulaire de
    demande dynamique, workflow d'approbation, cout : Phase 8). Deja
    utilisable comme filtre/qualification sur un ticket, et comme point
    d'accroche pour la CMDB (un service sera relie a des CI en Phase 6)."""
    _name = 'itsm.service'
    _description = "Service (catalogue)"
    _order = 'name'

    name = fields.Char(string="Nom", required=True, translate=True)
    active = fields.Boolean(default=True)
    description = fields.Text(string="Description")
    category_id = fields.Many2one('itsm.category', string="Catégorie")
    owner_team_id = fields.Many2one('itsm.team', string="Équipe propriétaire")
    default_sla_policy_id = fields.Many2one('itsm.sla.policy', string="SLA par défaut")
    icon = fields.Char(help="Classe d'icône (ex. fa-laptop) affichée dans le catalogue.")
    requires_approval = fields.Boolean(
        string="Nécessite une approbation",
        help="Toute demande sur ce service doit être approuvée avant de pouvoir être résolue "
             "(ex. matériel coûteux, accès sensible).",
    )
    ticket_count = fields.Integer(compute='_compute_ticket_count')

    def _compute_ticket_count(self):
        Ticket = self.env['itsm.ticket']
        for service in self:
            service.ticket_count = Ticket.search_count([('service_id', '=', service.id)])
