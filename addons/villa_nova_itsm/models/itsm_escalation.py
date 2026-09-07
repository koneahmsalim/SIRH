from odoo import fields, models


class ItsmEscalationLevel(models.Model):
    """Matrice d'escalade configurable par equipe - remplace le tunnel unique
    "responsable d'equipe des le depassement" par N paliers, chacun declenche
    apres un delai (en heures) suivant le depassement du SLA de resolution.
    Une equipe SANS niveau configure conserve l'ancien comportement (repli
    sur team.leader_id, voir itsm_ticket.py::_escalate_on_breach) - ajouter
    cette matrice ne casse aucune equipe deja en place."""
    _name = 'itsm.escalation.level'
    _description = "Niveau d'escalade SLA"
    _order = 'team_id, level'

    team_id = fields.Many2one('itsm.team', string="Équipe", required=True, ondelete='cascade', index=True)
    level = fields.Integer(string="Niveau", required=True, default=1)
    delay_hours = fields.Float(
        string="Délai après dépassement (h)", required=True, default=0.0,
        help="Ce niveau se déclenche quand le SLA de résolution est dépassé depuis au moins ce "
             "nombre d'heures. 0 = dès le dépassement.",
    )
    notify_user_id = fields.Many2one('res.users', string="Notifier", required=True)

    _sql_constraints = [
        ('level_positive', 'CHECK (level > 0)', "Le niveau doit être un entier positif."),
        ('delay_non_negative', 'CHECK (delay_hours >= 0)', "Le délai ne peut pas être négatif."),
        ('team_level_uniq', 'unique(team_id, level)', "Ce niveau existe déjà pour cette équipe."),
    ]
