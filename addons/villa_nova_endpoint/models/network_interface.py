from odoo import fields, models


class ItamNetworkInterface(models.Model):
    """Un poste peut avoir plusieurs interfaces (Ethernet + Wi-Fi + VPN...) -
    l'ancien champ plat maintenance.equipment.ip_address (Phase 5 decouverte)
    reste alimente avec l'IP de l'interface primaire pour ne rien casser des
    vues/listes existantes, cette table porte le detail complet par
    interface. Remplacee entierement a chaque check-in, comme les disques."""
    _name = 'itam.network.interface'
    _description = "Interface réseau (inventaire agent endpoint)"
    _order = 'equipment_id, is_primary desc, name'

    equipment_id = fields.Many2one('maintenance.equipment', string="Actif", required=True,
                                    ondelete='cascade', index=True)
    name = fields.Char(string="Nom", required=True)
    mac_address = fields.Char(string="Adresse MAC")
    ip_address = fields.Char(string="Adresse IP")
    subnet_mask = fields.Char(string="Masque de sous-réseau")
    gateway = fields.Char(string="Passerelle")
    dns_servers = fields.Char(string="Serveurs DNS")
    dhcp_enabled = fields.Boolean(string="DHCP activé")
    is_primary = fields.Boolean(string="Interface primaire")
