from odoo import api, fields, models

# Valeurs de repli, alignees sur le droit ivoirien (decret n°98-198 du 7 mars
# 1998 et art. 80 du Code du travail) : elles servent tant que la RH n'a rien
# saisi, et en cas de parametre supprime ou illisible.
DELAI_JUSTIFICATIF_DEFAUT = 24
DELAI_ABANDON_POSTE_DEFAUT = 72

PARAM_JUSTIFICATIF = 'villa_nova_leaves.delai_justificatif_heures'
PARAM_ABANDON_POSTE = 'villa_nova_leaves.delai_abandon_poste_heures'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    villa_nova_delai_justificatif = fields.Integer(
        string="Délai de remise du justificatif (heures)",
        config_parameter=PARAM_JUSTIFICATIF,
        default=DELAI_JUSTIFICATIF_DEFAUT,
        help="Temps laissé au collaborateur pour fournir un justificatif après "
             "la déclaration d'une absence non planifiée. Passé ce délai, une "
             "relance est adressée à la RH et au responsable hiérarchique.",
    )
    villa_nova_delai_abandon_poste = fields.Integer(
        string="Seuil d'alerte abandon de poste (heures)",
        config_parameter=PARAM_ABANDON_POSTE,
        default=DELAI_ABANDON_POSTE_DEFAUT,
        help="Durée d'absence non justifiée au-delà de laquelle une alerte est "
             "remontée à la Direction Générale. L'article 80 du Code du travail "
             "ivoirien retient 72 heures ; le système se contente d'alerter et "
             "ne prend aucune décision à la place de l'entreprise.",
    )

    def set_values(self):
        super().set_values()
        # Les echeances sont des champs calcules STOCKES : modifier le delai ne
        # les recalcule pas de lui-meme. On rafraichit donc les absences encore
        # en cours, sans quoi la RH verrait l'ancien delai s'appliquer sur des
        # dossiers ouverts apres avoir change le reglage.
        en_cours = self.env['hr.unplanned.absence'].search([
            ('state', 'in', ('declaree', 'alerte_abandon_poste')),
        ])
        if en_cours:
            en_cours._compute_deadlines()


class VillaNovaDelaisMixin(models.AbstractModel):
    """Acces centralise aux deux delais, pour ne pas disperser la lecture des
    parametres systeme (et leur repli) dans chaque methode qui en a besoin."""
    _name = 'villa.nova.delais.absence'
    _description = "Délais réglementaires applicables aux absences"

    @api.model
    def delai_justificatif_heures(self):
        return self._lire_delai(PARAM_JUSTIFICATIF, DELAI_JUSTIFICATIF_DEFAUT)

    @api.model
    def delai_abandon_poste_heures(self):
        return self._lire_delai(PARAM_ABANDON_POSTE, DELAI_ABANDON_POSTE_DEFAUT)

    @api.model
    def _lire_delai(self, cle, defaut):
        valeur = self.env['ir.config_parameter'].sudo().get_param(cle)
        try:
            heures = int(valeur)
        except (TypeError, ValueError):
            return defaut
        # Un delai nul ou negatif ferait expirer l'echeance avant meme la
        # declaration : on revient au defaut plutot que de produire des
        # relances immediates et incomprehensibles.
        return heures if heures > 0 else defaut
