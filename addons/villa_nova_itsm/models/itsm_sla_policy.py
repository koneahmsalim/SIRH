from odoo import api, fields, models

PRIORITY_SELECTION = [
    ('low', "Basse"),
    ('medium', "Moyenne"),
    ('high', "Haute"),
    ('critical', "Critique"),
]


class ItsmSlaPolicy(models.Model):
    """Politique SLA nommee (ex. "SLA Standard") contenant une ligne par
    priorite (temps de premiere reponse / resolution). Le calcul reel des
    echeances se fait sur le calendrier de travail (resource.calendar,
    natif) pour ne compter que les heures ouvrees - voir itsm.ticket
    pour l'application concrete."""
    _name = 'itsm.sla.policy'
    _description = "Politique SLA"
    _order = 'name'

    name = fields.Char(string="Nom", required=True)
    active = fields.Boolean(default=True)
    description = fields.Text(string="Description")
    calendar_id = fields.Many2one(
        'resource.calendar', string="Calendrier",
        help="Calendrier de travail utilisé pour ce SLA. Si vide, celui de l'équipe du ticket est utilisé, "
             "sinon celui de la société.",
    )
    line_ids = fields.One2many('itsm.sla.policy.line', 'sla_policy_id', string="Cibles par priorité")

    def _get_line(self, priority):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: l.priority == priority)[:1]


class ItsmSlaPolicyLine(models.Model):
    _name = 'itsm.sla.policy.line'
    _description = "Cible SLA par priorité"
    _order = 'sla_policy_id, sequence'

    sla_policy_id = fields.Many2one('itsm.sla.policy', required=True, ondelete='cascade')
    sequence = fields.Integer(compute='_compute_sequence', store=True)
    priority = fields.Selection(PRIORITY_SELECTION, required=True)
    first_response_hours = fields.Float(string="Première réponse (h)", required=True, default=4.0)
    resolution_hours = fields.Float(string="Résolution (h)", required=True, default=24.0)

    _sql_constraints = [
        ('policy_priority_uniq', 'unique (sla_policy_id, priority)',
         "Cette politique a déjà une cible pour cette priorité."),
    ]

    @api.depends('priority')
    def _compute_sequence(self):
        order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        for line in self:
            line.sequence = order.get(line.priority, 4)
