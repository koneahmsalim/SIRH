from datetime import timedelta

from odoo import api, fields, models

WARRANTY_SOON_DAYS = 60

ASSET_STATUS_SELECTION = [
    ('in_stock', "En stock"),
    ('assigned', "Affecté"),
    ('in_repair', "En réparation"),
    ('retired', "Retiré"),
    ('disposed', "Mis au rebut"),
]

WARRANTY_STATUS_SELECTION = [
    ('none', "Non renseignée"),
    ('valid', "Valide"),
    ('expiring_soon', "Expire bientôt"),
    ('expired', "Expirée"),
]


class MaintenanceEquipment(models.Model):
    """Etend le module natif Maintenance (deja mature : categories, garantie,
    proprietes personnalisees, cout, historique de demandes) plutot que de
    reconstruire un modele d'actif depuis zero - conformement au choix
    d'architecture confirme avec l'utilisateur pour la Phase 4 ITAM."""
    _inherit = 'maintenance.equipment'

    asset_tag = fields.Char(string="Référence actif", copy=False, readonly=True, index=True)
    # employee_id est deja fourni par le module natif hr_maintenance (deja
    # installe dans ce SIRH) - reutilise tel quel plutot que duplique, avec
    # equipment_assign_to (employe/departement/autre) qui pilote aussi le
    # owner_user_id natif.
    asset_status = fields.Selection(
        ASSET_STATUS_SELECTION, string="Statut de l'actif", default='in_stock',
        required=True, tracking=True,
    )
    purchase_date = fields.Date(string="Date d'achat")
    invoice_reference = fields.Char(string="Référence facture")

    warranty_status = fields.Selection(
        WARRANTY_STATUS_SELECTION, string="Statut de garantie",
        compute='_compute_warranty_status', store=True,
    )

    ticket_ids = fields.One2many('itsm.ticket', 'equipment_id', string="Tickets")
    ticket_count = fields.Integer(string="Nombre de tickets", compute='_compute_ticket_count')

    @api.depends('warranty_date')
    def _compute_warranty_status(self):
        today = fields.Date.context_today(self)
        for equipment in self:
            if not equipment.warranty_date:
                equipment.warranty_status = 'none'
            elif equipment.warranty_date < today:
                equipment.warranty_status = 'expired'
            elif equipment.warranty_date <= today + timedelta(days=WARRANTY_SOON_DAYS):
                equipment.warranty_status = 'expiring_soon'
            else:
                equipment.warranty_status = 'valid'

    def _compute_ticket_count(self):
        for equipment in self:
            equipment.ticket_count = len(equipment.ticket_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('asset_tag'):
                vals['asset_tag'] = self.env['ir.sequence'].next_by_code('maintenance.equipment.asset_tag') or False
        return super().create(vals_list)

    def action_view_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'itsm.ticket',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {'default_equipment_id': self.id},
        }
