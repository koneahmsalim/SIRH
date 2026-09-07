from odoo import api, fields, models

from ..models.remote_command import COMMAND_TYPE_SELECTION, PARAMETER_REQUIRED_TYPES, SENSITIVE_COMMAND_TYPES


class ItsmRemoteCommandWizard(models.TransientModel):
    """Envoi rapide d'une commande a distance en UN clic depuis la fiche de
    l'actif - remplace le circuit precedent (ouvrir la liste des commandes,
    creer, remplir, enregistrer, soumettre, confirmer) juge trop lourd par
    l'utilisateur pour une action aussi simple qu'un redemarrage."""
    _name = 'itsm.remote.command.wizard'
    _description = "Envoyer une commande à distance"

    equipment_id = fields.Many2one('maintenance.equipment', string="Actif", required=True, readonly=True)
    command_type = fields.Selection(COMMAND_TYPE_SELECTION, string="Commande", required=True)
    parameters = fields.Char(
        string="Paramètre",
        help="Nom du service (vérifier/redémarrer un service) ou message à afficher (notifier l'utilisateur).",
    )
    script_id = fields.Many2one('itsm.approved.script', string="Script à exécuter",
                                 domain=[('active', '=', True)])
    is_sensitive = fields.Boolean(string="Action sensible", compute='_compute_is_sensitive')
    parameter_required = fields.Boolean(compute='_compute_is_sensitive')

    @api.depends('command_type')
    def _compute_is_sensitive(self):
        for wizard in self:
            wizard.is_sensitive = wizard.command_type in SENSITIVE_COMMAND_TYPES
            wizard.parameter_required = wizard.command_type in PARAMETER_REQUIRED_TYPES

    def action_send(self):
        self.ensure_one()
        command = self.env['itsm.remote.command'].create({
            'equipment_id': self.equipment_id.id,
            'command_type': self.command_type,
            'parameters': self.parameters,
            'script_id': self.script_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': command.name,
            'res_model': 'itsm.remote.command',
            'view_mode': 'form',
            'res_id': command.id,
            'target': 'current',
        }
