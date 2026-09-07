import hashlib

from odoo import api, fields, models

SCRIPT_TYPE_SELECTION = [
    ('powershell', "PowerShell"),
]


class ItsmApprovedScript(models.Model):
    """Bibliotheque de scripts CURES PAR UN ADMIN, seule forme de code
    executable a distance dans ce projet - tout l'inverse d'un execute-code
    generique. Le contenu approuve est FIGE au moment de la soumission d'une
    commande (voir itsm.remote.command.pinned_script_hash/pinned_script_content) :
    editer un script ici n'affecte JAMAIS une commande deja soumise, seules
    les FUTURES soumissions verront le nouveau contenu - une modification
    non revue ne peut donc jamais s'executer silencieusement sur un poste."""
    _name = 'itsm.approved.script'
    _description = "Script approuvé (bibliothèque RMM)"
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string="Nom", required=True, tracking=True)
    description = fields.Text(string="Description", help="À quoi sert ce script, quand l'utiliser.")
    script_type = fields.Selection(SCRIPT_TYPE_SELECTION, string="Type", default='powershell', required=True)
    content = fields.Text(string="Contenu du script", required=True, tracking=True)
    content_hash = fields.Char(string="Empreinte SHA-256", compute='_compute_content_hash', store=True, readonly=True)
    active = fields.Boolean(string="Actif", default=True)
    created_by = fields.Many2one('res.users', string="Créé par", default=lambda self: self.env.user, readonly=True)

    usage_count = fields.Integer(string="Nombre d'utilisations", compute='_compute_usage_count')

    @api.depends('content')
    def _compute_content_hash(self):
        for script in self:
            content = script.content or ''
            script.content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _compute_usage_count(self):
        Command = self.env['itsm.remote.command']
        for script in self:
            script.usage_count = Command.search_count([('script_id', '=', script.id)])

    def action_view_usage(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'itsm.remote.command',
            'view_mode': 'list,form',
            'domain': [('script_id', '=', self.id)],
        }
