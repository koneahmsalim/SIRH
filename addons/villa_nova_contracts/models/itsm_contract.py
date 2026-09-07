from datetime import timedelta

from odoo import _, api, fields, models

RENEWAL_SOON_DAYS = 30

CONTRACT_TYPE_SELECTION = [
    ('support', "Support"),
    ('maintenance', "Maintenance"),
    ('license', "Licence"),
    ('service', "Service"),
    ('warranty_extension', "Extension de garantie"),
]

RENEWAL_STATUS_SELECTION = [
    ('none', "Non renseigné"),
    ('valid', "Valide"),
    ('expiring_soon', "Expire bientôt"),
    ('expired', "Expiré"),
]


class ItsmContract(models.Model):
    _name = 'itsm.contract'
    _description = "Contrat (support, maintenance, licence)"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'end_date'

    name = fields.Char(string="Nom", required=True, tracking=True)
    contract_type = fields.Selection(CONTRACT_TYPE_SELECTION, string="Type", default='support', required=True)
    vendor_id = fields.Many2one('res.partner', string="Fournisseur", required=True, tracking=True)
    reference = fields.Char(string="Référence contrat")
    responsible_id = fields.Many2one('res.users', string="Responsable", default=lambda self: self.env.user)

    start_date = fields.Date(string="Date de début", required=True, default=fields.Date.context_today)
    end_date = fields.Date(string="Date de fin", required=True, tracking=True)
    cost = fields.Float(string="Coût")
    auto_renew = fields.Boolean(string="Renouvellement automatique")
    renewal_status = fields.Selection(
        RENEWAL_STATUS_SELECTION, string="Statut", compute='_compute_renewal_status', store=True,
    )

    equipment_ids = fields.Many2many(
        'maintenance.equipment', 'itsm_contract_equipment_rel', 'contract_id', 'equipment_id',
        string="Actifs couverts",
    )
    equipment_count = fields.Integer(string="Nombre d'actifs", compute='_compute_equipment_count')
    license_ids = fields.Many2many('itam.software.license', string="Licences couvertes")

    purchase_order_id = fields.Many2one('purchase.order', string="Bon de commande d'origine")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True)

    @api.depends('end_date')
    def _compute_renewal_status(self):
        today = fields.Date.context_today(self)
        for contract in self:
            if not contract.end_date:
                contract.renewal_status = 'none'
            elif contract.end_date < today:
                contract.renewal_status = 'expired'
            elif contract.end_date <= today + timedelta(days=RENEWAL_SOON_DAYS):
                contract.renewal_status = 'expiring_soon'
            else:
                contract.renewal_status = 'valid'

    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        for contract in self:
            contract.equipment_count = len(contract.equipment_ids)

    def action_view_equipment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Actifs couverts"),
            'res_model': 'maintenance.equipment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.equipment_ids.ids)],
        }
