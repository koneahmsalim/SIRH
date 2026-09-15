from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

# Bareme de preavis de la Convention Collective Interprofessionnelle ivoirienne
# (art. 34), applique aux articles 18.4 a 18.6 du Code du travail. Le preavis
# depend de la SEULE anciennete, pas de la categorie professionnelle - point
# souvent mal compris, d'ou son rappel a l'ecran plutot que dans une note.
# Chaque palier : (anciennete strictement inferieure a N mois, libelle).
BAREME_PREAVIS_CCI = [
    (12, "8 jours"),
    (24, "15 jours"),
    (36, "21 jours"),
    (72, "1 mois"),
    (132, "2 mois"),
    (192, "3 mois"),
]
PREAVIS_MAXIMUM = "4 mois"

# Duree du preavis convertie en jours calendaires, pour proposer une date de
# depart coherente avec le bareme.
DUREE_EN_JOURS = {
    "8 jours": 8,
    "15 jours": 15,
    "21 jours": 21,
    "1 mois": 30,
    "2 mois": 60,
    "3 mois": 90,
    "4 mois": 120,
}


class HrResignation(models.Model):
    _inherit = 'hr.resignation'

    x_anciennete_mois = fields.Integer(
        string="Ancienneté (mois)",
        compute='_compute_villa_nova_preavis',
        help="Ancienneté révolue à la date de la demande, exprimée en mois entiers.",
    )
    x_preavis_legal = fields.Char(
        string="Préavis légal (CCI art. 34)",
        compute='_compute_villa_nova_preavis',
        help="Durée minimale de préavis fixée par la Convention Collective "
             "Interprofessionnelle, en fonction de la seule ancienneté. "
             "Un accord entre les parties peut allonger ce délai, jamais le réduire.",
    )
    x_date_fin_preavis = fields.Date(
        string="Fin de préavis au plus tôt",
        compute='_compute_villa_nova_preavis',
        help="Date de départ résultant de l'application stricte du préavis légal, "
             "à comparer avec la date de départ souhaitée.",
    )

    @api.depends('joined_date', 'resign_confirm_date')
    def _compute_villa_nova_preavis(self):
        for demande in self:
            debut = demande.joined_date
            reference = demande.resign_confirm_date or fields.Date.context_today(demande)
            if not debut or reference < debut:
                demande.x_anciennete_mois = 0
                demande.x_preavis_legal = False
                demande.x_date_fin_preavis = False
                continue
            ecart = relativedelta(reference, debut)
            mois = ecart.years * 12 + ecart.months
            demande.x_anciennete_mois = mois
            libelle = next(
                (lib for seuil, lib in BAREME_PREAVIS_CCI if mois < seuil),
                PREAVIS_MAXIMUM,
            )
            demande.x_preavis_legal = libelle
            demande.x_date_fin_preavis = reference + relativedelta(
                days=DUREE_EN_JOURS.get(libelle, 0),
            )
