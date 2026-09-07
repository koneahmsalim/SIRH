from odoo import _, fields, models


class ResPartner(models.Model):
    """Visibilite fournisseur pour l'ITAM - ajoute des compteurs sur la
    fiche contact existante plutot que de construire une fiche
    "fournisseur" separee redondante avec res.partner."""
    _inherit = 'res.partner'

    itam_equipment_count = fields.Integer(string="Actifs fournis", compute='_compute_itam_vendor_counts')
    itsm_contract_count = fields.Integer(string="Contrats", compute='_compute_itam_vendor_counts')

    def _compute_itam_vendor_counts(self):
        Equipment = self.env['maintenance.equipment']
        Contract = self.env['itsm.contract']
        for partner in self:
            partner.itam_equipment_count = Equipment.search_count([('partner_id', '=', partner.id)])
            partner.itsm_contract_count = Contract.search_count([('vendor_id', '=', partner.id)])

    def action_view_itam_equipment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Actifs fournis"),
            'res_model': 'maintenance.equipment',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
        }

    def action_view_itsm_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Contrats"),
            'res_model': 'itsm.contract',
            'view_mode': 'list,form',
            'domain': [('vendor_id', '=', self.id)],
        }
