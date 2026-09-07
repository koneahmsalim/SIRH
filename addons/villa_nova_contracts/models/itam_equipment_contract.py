from odoo import fields, models


class MaintenanceEquipment(models.Model):
    """Tracabilite achat -> actif : lie l'actif au bon de commande natif
    (module purchase, deja installe) plutot que de dupliquer un champ
    "fournisseur/prix d'achat" independant - ajoute via _inherit comme le
    reste des extensions ITAM."""
    _inherit = 'maintenance.equipment'

    purchase_order_id = fields.Many2one('purchase.order', string="Bon de commande d'origine")
    contract_ids = fields.Many2many(
        'itsm.contract', 'itsm_contract_equipment_rel', 'equipment_id', 'contract_id',
        string="Contrats associés",
    )
    contract_count = fields.Integer(string="Nombre de contrats", compute='_compute_contract_count')

    def _compute_contract_count(self):
        for equipment in self:
            equipment.contract_count = len(equipment.contract_ids)

    def action_view_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Contrats",
            'res_model': 'itsm.contract',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.contract_ids.ids)],
        }
