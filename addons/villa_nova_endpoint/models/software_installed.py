from odoo import fields, models

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
