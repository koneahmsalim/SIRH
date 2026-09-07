from datetime import timedelta

from odoo import api, fields, models

RENEWAL_SOON_DAYS = 60

LICENSE_TYPE_SELECTION = [
    ('per_seat', "Par utilisateur"),
    ('per_device', "Par appareil"),
    ('subscription', "Abonnement"),
    ('perpetual', "Perpétuelle"),
    ('open_source', "Open source"),
]

RENEWAL_STATUS_SELECTION = [
    ('none', "Non applicable"),
    ('valid', "Valide"),
    ('expiring_soon', "Expire bientôt"),
    ('expired', "Expirée"),
]


class ItamSoftwareLicense(models.Model):
    _name = 'itam.software.license'
    _description = "Licence logicielle"
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string="Logiciel", required=True, tracking=True)
    vendor_id = fields.Many2one('res.partner', string="Éditeur / Fournisseur")
    license_type = fields.Selection(
        LICENSE_TYPE_SELECTION, string="Type de licence", default='per_seat', required=True,
    )
    license_key = fields.Char(string="Clé de licence / référence")
    active = fields.Boolean(default=True)

    seats_total = fields.Integer(string="Sièges achetés", default=1)
    seats_used = fields.Integer(string="Sièges utilisés", compute='_compute_seats', store=True)
    seats_available = fields.Integer(string="Sièges disponibles", compute='_compute_seats', store=True)
    is_over_allocated = fields.Boolean(string="Sur-allocation", compute='_compute_seats', store=True)

    cost = fields.Float(string="Coût")
    purchase_date = fields.Date(string="Date d'achat")
    expiration_date = fields.Date(string="Date d'expiration")
    renewal_status = fields.Selection(
        RENEWAL_STATUS_SELECTION, string="Statut de renouvellement",
        compute='_compute_renewal_status', store=True, index=True,
    )

    notes = fields.Text(string="Notes")
    assignment_ids = fields.One2many('itam.software.assignment', 'license_id', string="Attributions")

    @api.depends('seats_total', 'assignment_ids.active')
    def _compute_seats(self):
        for license in self:
            used = len(license.assignment_ids.filtered('active'))
            license.seats_used = used
            license.seats_available = license.seats_total - used
            license.is_over_allocated = used > license.seats_total

    @api.depends('expiration_date')
    def _compute_renewal_status(self):
        today = fields.Date.context_today(self)
        for license in self:
            if not license.expiration_date:
                license.renewal_status = 'none'
            elif license.expiration_date < today:
                license.renewal_status = 'expired'
            elif license.expiration_date <= today + timedelta(days=RENEWAL_SOON_DAYS):
                license.renewal_status = 'expiring_soon'
            else:
                license.renewal_status = 'valid'
