from odoo import fields, models


class ItsmApproval(models.Model):
    """Meme generalisation localisee que villa_nova_change/itsm_approval_change.py :
    ajoute remote_command_id au moteur d'approbation existant et surcharge
    _get_approval_target(), sans toucher au reste (action_approve/
    action_refuse generiques reutilises tels quels).

    Pas de contrainte SQL "cible requise" : ce moteur est etendu par
    plusieurs modules independants (villa_nova_change, ce module,
    villa_nova_contracts...) qui ne se connaissent pas entre eux - un CHECK
    partage par nom se ferait ecraser par le dernier module charge et
    casserait les lignes des autres cibles (colonne inexistante si ce
    module n'est pas installe). Voir le meme commentaire, plus detaille,
    dans villa_nova_change/itsm_approval_change.py."""
    _inherit = 'itsm.approval'

    remote_command_id = fields.Many2one('itsm.remote.command', string="Commande à distance",
                                         ondelete='cascade', index=True)

    def _get_approval_target(self):
        self.ensure_one()
        return self.remote_command_id or super()._get_approval_target()

    def action_approve(self):
        super().action_approve()
        for approval in self:
            if approval.remote_command_id and approval.state == 'approved':
                approval.remote_command_id.write({'state': 'pending'})

    def action_refuse(self):
        super().action_refuse()
        for approval in self:
            if approval.remote_command_id and approval.state == 'refused':
                approval.remote_command_id.write({'state': 'refused'})
