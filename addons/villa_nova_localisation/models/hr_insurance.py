from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class InsurancePolicy(models.Model):
    _inherit = 'insurance.policy'

    x_part_employeur_pct = fields.Float(
        string="Part employeur (%)",
        default=100.0,
        help="Pourcentage de la cotisation totale à la charge de l'employeur. "
             "Le solde est retenu sur le salaire du collaborateur.\n"
             "Exemples ivoiriens : CMU 50 % (forfait de 1 000 F réparti 500/500), "
             "CNPS vieillesse 55 % (7,70 % employeur sur 14 % au total), "
             "prestations familiales et accidents du travail 100 % "
             "(intégralement à la charge de l'employeur).",
    )


class HrInsurance(models.Model):
    _inherit = 'hr.insurance'

    # Le champ natif "amount" porte la cotisation TOTALE. Rien n'indiquait
    # comment elle se repartissait, ce qui a fait lire les 1 000 F de la CMU
    # comme un montant errone alors qu'il s'agit du forfait complet, dont
    # seuls 500 F sont retenus sur le salaire. Les deux parts sont donc
    # desormais affichees explicitement, plutot que laissees a l'interpretation.
    x_part_employeur = fields.Monetary(
        string="Part employeur",
        compute='_compute_villa_nova_parts', store=True, readonly=False,
        help="Montant supporté par l'entreprise. Pré-rempli d'après le taux du "
             "régime, modifiable au cas par cas.",
    )
    x_part_salarie = fields.Monetary(
        string="Part salarié",
        compute='_compute_villa_nova_parts', store=True, readonly=False,
        help="Montant retenu sur le bulletin de paie du collaborateur.",
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', string="Devise",
    )

    @api.depends('amount', 'policy_id.x_part_employeur_pct')
    def _compute_villa_nova_parts(self):
        for ligne in self:
            taux = (ligne.policy_id.x_part_employeur_pct or 0.0) / 100.0
            employeur = round(ligne.amount * taux)
            ligne.x_part_employeur = employeur
            # Le solde plutot qu'un second arrondi : la somme des deux parts
            # doit retomber exactement sur le total, sans franc perdu.
            ligne.x_part_salarie = ligne.amount - employeur

    @api.constrains('amount', 'x_part_employeur', 'x_part_salarie')
    def _check_villa_nova_repartition(self):
        for ligne in self:
            if abs((ligne.x_part_employeur + ligne.x_part_salarie) - ligne.amount) > 0.01:
                raise ValidationError(_(
                    "La répartition ne correspond pas au montant total de la cotisation "
                    "« %(regime)s » :\n"
                    "part employeur %(emp)s + part salarié %(sal)s = %(somme)s, "
                    "alors que le total est de %(total)s.",
                    regime=ligne.policy_id.name or '-',
                    emp=ligne.x_part_employeur, sal=ligne.x_part_salarie,
                    somme=ligne.x_part_employeur + ligne.x_part_salarie,
                    total=ligne.amount,
                ))
