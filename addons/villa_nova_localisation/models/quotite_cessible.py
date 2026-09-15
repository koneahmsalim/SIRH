from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Bareme de la quotite cessible, decret n° 2014-370 du 18 juin 2014 (art. 4).
# Tranches NON cumulatives : le taux de la tranche atteinte s'applique a la
# totalite du revenu, et non par paliers successifs.
# (plafond de la tranche en FCFA, taux applicable)
BAREME_QUOTITE_CESSIBLE = [
    (200000, 0.35),
    (400000, 0.38),
    (600000, 0.42),
    (800000, 0.45),
    (1000000, 0.48),
    (1500000, 0.52),
    (2000000, 0.55),
]
TAUX_QUOTITE_CESSIBLE_MAX = 0.57

# Quotite saisissable (art. 3 du meme decret) : plafond unique de 33 %.
# Elle borne les retenues subies, la quotite cessible bornant celles que le
# salarie consent lui-meme (cession volontaire).
TAUX_QUOTITE_SAISISSABLE = 0.33


def taux_quotite_cessible(revenu_mensuel):
    """Taux de cession applicable a un revenu mensuel, selon le bareme."""
    if not revenu_mensuel or revenu_mensuel <= 0:
        return 0.0
    for plafond, taux in BAREME_QUOTITE_CESSIBLE:
        if revenu_mensuel <= plafond:
            return taux
    return TAUX_QUOTITE_CESSIBLE_MAX


class SalaryAdvance(models.Model):
    _inherit = 'salary.advance'

    x_salaire_reference = fields.Monetary(
        string="Salaire de référence",
        compute='_compute_villa_nova_quotite',
        help="Salaire mensuel porté par le contrat de travail en cours, base de "
             "calcul de la quotité cessible.",
    )
    x_taux_quotite_cessible = fields.Float(
        string="Quotité cessible applicable (%)",
        compute='_compute_villa_nova_quotite',
        help="Taux issu du barème du décret n° 2014-370 du 18 juin 2014 (art. 4), "
             "fonction de la tranche de revenu.",
    )
    x_avance_maximum = fields.Monetary(
        string="Avance maximale autorisée",
        compute='_compute_villa_nova_quotite',
        help="Montant au-delà duquel l'avance dépasserait la quotité cessible du "
             "salarié. Rappel : l'article 34.1 du Code du travail interdit toute "
             "rémunération de l'avance sur salaire — aucun intérêt ne peut être "
             "appliqué.",
    )

    @api.depends('employee_id', 'employee_contract_id')
    def _compute_villa_nova_quotite(self):
        for demande in self:
            contrat = demande.employee_contract_id
            if not contrat:
                contrat = self.env['hr.contract'].search([
                    ('employee_id', '=', demande.employee_id.id),
                    ('state', '=', 'open'),
                ], limit=1)
            salaire = contrat.wage if contrat else 0.0
            taux = taux_quotite_cessible(salaire)
            demande.x_salaire_reference = salaire
            demande.x_taux_quotite_cessible = taux * 100
            demande.x_avance_maximum = salaire * taux

    @api.constrains('advance', 'employee_id', 'employee_contract_id')
    def _check_villa_nova_quotite_cessible(self):
        for demande in self:
            # Sans contrat rattache, le plafond n'est pas calculable : on laisse
            # passer plutot que de bloquer une saisie legitime sur une donnee
            # absente. Tant que la reprise des contrats n'est pas faite, le
            # controle ne peut pas etre exhaustif - et un blocage aveugle serait
            # plus nuisible qu'utile.
            if not demande.x_avance_maximum:
                continue
            if demande.advance > demande.x_avance_maximum:
                raise ValidationError(_(
                    "L'avance demandée (%(demande)s) dépasse la quotité cessible de "
                    "%(salarie)s.\n\n"
                    "Salaire de référence : %(salaire)s\n"
                    "Quotité cessible applicable : %(taux).0f %% "
                    "(décret n° 2014-370 du 18 juin 2014, art. 4)\n"
                    "Avance maximale autorisée : %(maximum)s",
                    demande="{:,.0f} FCFA".format(demande.advance).replace(',', ' '),
                    salarie=demande.employee_id.name,
                    salaire="{:,.0f} FCFA".format(demande.x_salaire_reference).replace(',', ' '),
                    taux=demande.x_taux_quotite_cessible,
                    maximum="{:,.0f} FCFA".format(demande.x_avance_maximum).replace(',', ' '),
                ))


class HrLoan(models.Model):
    _inherit = 'hr.loan'

    x_mensualite = fields.Monetary(
        string="Mensualité de remboursement",
        compute='_compute_villa_nova_quotite_pret',
        help="Montant prélevé chaque mois sur le salaire, soit le montant du prêt "
             "divisé par le nombre d'échéances.",
    )
    x_mensualite_maximum = fields.Monetary(
        string="Mensualité maximale autorisée",
        compute='_compute_villa_nova_quotite_pret',
        help="Plafond de retenue mensuelle résultant de la quotité cessible du "
             "salarié (décret n° 2014-370, art. 4).",
    )

    @api.depends('loan_amount', 'installment', 'employee_id')
    def _compute_villa_nova_quotite_pret(self):
        Contract = self.env['hr.contract']
        for pret in self:
            pret.x_mensualite = (
                pret.loan_amount / pret.installment if pret.installment else 0.0
            )
            contrat = Contract.search([
                ('employee_id', '=', pret.employee_id.id),
                ('state', '=', 'open'),
            ], limit=1)
            salaire = contrat.wage if contrat else 0.0
            pret.x_mensualite_maximum = salaire * taux_quotite_cessible(salaire)

    @api.constrains('loan_amount', 'installment', 'employee_id')
    def _check_villa_nova_quotite_pret(self):
        for pret in self:
            if not pret.x_mensualite_maximum:
                continue
            if pret.x_mensualite > pret.x_mensualite_maximum:
                raise ValidationError(_(
                    "La mensualité de remboursement (%(mensualite)s) dépasse la quotité "
                    "cessible de %(salarie)s (%(maximum)s au maximum).\n\n"
                    "Augmentez le nombre d'échéances ou réduisez le montant du prêt.\n"
                    "Référence : décret n° 2014-370 du 18 juin 2014, art. 4.",
                    mensualite="{:,.0f} FCFA".format(pret.x_mensualite).replace(',', ' '),
                    salarie=pret.employee_id.name,
                    maximum="{:,.0f} FCFA".format(pret.x_mensualite_maximum).replace(',', ' '),
                ))
