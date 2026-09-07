from odoo import api, fields, models

SOURCE_SELECTION = [
    ('registry', "Registre Windows"),
    ('wmi', "WMI"),
    ('manual', "Manuel"),
]


class ItamSoftwareInstalled(models.Model):
    """Inventaire logiciel REEL remonte par l'agent (enumeration du registre
    HKLM\\...\\Uninstall + WOW6432Node - deliberement pas Win32_Product/WMI,
    connu pour declencher des reparations MSI en effet de bord et etre lent).
    Distinct de itam.software.license (Phase 5 - catalogue de licences
    achetees/attributions) : ceci decrit ce qui est REELLEMENT installe sur
    CE poste, pas ce qui est sous licence. Remplace entierement a chaque
    check-in (comme les disques/interfaces), jamais d'accumulation."""
    _name = 'itam.software.installed'
    _description = "Logiciel installé (inventaire agent endpoint)"
    _order = 'equipment_id, name'

    equipment_id = fields.Many2one('maintenance.equipment', string="Actif", required=True,
                                    ondelete='cascade', index=True)
    name = fields.Char(string="Nom", required=True)
    version = fields.Char(string="Version")
    publisher = fields.Char(string="Éditeur")
    install_date = fields.Date(string="Date d'installation")
    source = fields.Selection(SOURCE_SELECTION, string="Source", default='registry')

    is_licensed = fields.Boolean(
        string="Sous licence suivie", compute='_compute_is_licensed', search='_search_is_licensed',
        help="Rapprochement par nom avec le catalogue de licences (Phase 5) - heuristique "
             "(correspondance exacte ou partielle, insensible à la casse), pas une garantie "
             "juridique de conformité. À vérifier manuellement avant toute conclusion d'audit.",
    )

    @api.depends('name')
    def _compute_is_licensed(self):
        license_names = [n.lower() for n in self.env['itam.software.license'].search([]).mapped('name') if n]
        for line in self:
            name = (line.name or '').lower()
            line.is_licensed = bool(name) and any(
                name == ln or ln in name or name in ln for ln in license_names)

    @api.model
    def _search_is_licensed(self, operator, value):
        # Rapprochement flou impossible a exprimer en SQL pur : calcule en
        # Python puis filtre par IDs - volume attendu (quelques centaines a
        # quelques milliers de lignes par poste x parc) largement compatible
        # avec cette approche, pas besoin d'une vue SQL dediee.
        if operator not in ('=', '!='):
            raise NotImplementedError
        want_licensed = value if operator == '=' else not value
        matching_ids = self.search([]).filtered(lambda l: l.is_licensed == want_licensed).ids
        return [('id', 'in', matching_ids)]
