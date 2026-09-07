from odoo import fields, models


class ItsmApproval(models.Model):
    """Generalisation localisee annoncee des la Phase 3 : ajoute change_id
    au moteur d'approbation existant et surcharge _get_approval_target()
    plutot que de reconstruire le modele - le reste (action_approve/
    action_refuse, les etats) est reutilise tel quel."""
    _inherit = 'itsm.approval'

    change_id = fields.Many2one('itsm.change', string="Changement", ondelete='cascade', index=True)

    # Pas de CHECK SQL "au moins une cible requise" ici : ce moteur est
    # desormais etendu par plusieurs modules INDEPENDANTS les uns des autres
    # (villa_nova_change, villa_nova_endpoint, villa_nova_contracts...) qui
    # ne se connaissent pas entre eux. Un CHECK partage par nom se ferait
    # ecraser par le dernier module charge et casserait retroactivement les
    # lignes des AUTRES cibles (colonne inexistante si ce module n'est pas
    # installe, ou condition trop etroite sinon) - constate en pratique en
    # ajoutant la 3e extension. Une cible manquante est inoffensive
    # (_get_approval_target renvoie un recordset vide, action_approve/
    # action_refuse verifient deja `if target:` avant d'agir).
    def _get_approval_target(self):
        self.ensure_one()
        return self.change_id or super()._get_approval_target()
