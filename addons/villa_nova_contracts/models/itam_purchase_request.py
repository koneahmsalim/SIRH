from odoo import _, api, fields, models
from odoo.exceptions import UserError

STATE_SELECTION = [
    ('draft', "Brouillon"),
    ('submitted', "Soumise"),
    ('approved', "Approuvée"),
    ('refused', "Refusée"),
    ('ordered', "Commandée"),
    ('cancelled', "Annulée"),
]

_ALLOWED_TRANSITIONS = {
    'draft': {'submitted', 'cancelled'},
    'submitted': {'approved', 'refused', 'cancelled'},
    'approved': {'ordered', 'cancelled'},
    'refused': {'draft', 'cancelled'},
    'ordered': set(),
    'cancelled': set(),
}


class ItamPurchaseRequest(models.Model):
    """Demande d'achat -> approbation -> bon de commande : gap identifie par
    rapport a ServiceDesk Plus (gestion des achats/PO integree a l'ITAM).
    Avant ce modele, seule la TRACABILITE existait (itsm.contract.
    purchase_order_id pointe vers un bon de commande deja cree ailleurs) -
    ceci ajoute le VRAI circuit qui en genere un. Reutilise le moteur
    d'approbation existant (itsm.approval) comme les autres extensions du
    projet plutot que d'en construire un nouveau."""
    _name = 'itam.purchase.request'
    _description = "Demande d'achat"
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(string="Référence", default="Nouveau", copy=False, readonly=True)
    requested_by = fields.Many2one('res.users', string="Demandé par", default=lambda self: self.env.user,
                                    required=True, readonly=True)
    request_date = fields.Datetime(string="Demandé le", default=fields.Datetime.now, readonly=True)
    justification = fields.Text(string="Justification")
    vendor_id = fields.Many2one('res.partner', string="Fournisseur",
                                 help="Requis avant de générer le bon de commande.")
    state = fields.Selection(STATE_SELECTION, string="Statut", default='draft', required=True,
                              tracking=True, index=True)

    line_ids = fields.One2many('itam.purchase.request.line', 'request_id', string="Lignes")
    total_estimated_cost = fields.Monetary(string="Coût estimé total", compute='_compute_total_estimated_cost',
                                            currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    approval_id = fields.Many2one('itsm.approval', string="Approbation", copy=False, readonly=True)
    purchase_order_id = fields.Many2one('purchase.order', string="Bon de commande généré", copy=False, readonly=True)

    @api.depends('line_ids.subtotal')
    def _compute_total_estimated_cost(self):
        for request in self:
            request.total_estimated_cost = sum(request.line_ids.mapped('subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('itam.purchase.request') or 'Nouveau'
        return super().create(vals_list)

    def _check_state_transition(self, old_state, new_state):
        if old_state == new_state:
            return
        allowed = _ALLOWED_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise UserError(_(
                "Transition non autorisée : %(old)s → %(new)s.",
                old=dict(STATE_SELECTION).get(old_state), new=dict(STATE_SELECTION).get(new_state)))

    def write(self, vals):
        if 'state' in vals:
            for request in self:
                self._check_state_transition(request.state, vals['state'])
        return super().write(vals)

    def action_submit(self):
        for request in self:
            request._submit_one()

    def _submit_one(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Ajoutez au moins une ligne avant de soumettre la demande."))
        managers = self.env.ref('villa_nova_itam.group_itam_manager').users.filtered(
            lambda u: u.id != self.requested_by.id and u.email)
        if not managers:
            raise UserError(_(
                "Aucun autre gestionnaire ITAM actif pour approuver cette demande."))
        approval = self.env['itsm.approval'].create({
            'purchase_request_id': self.id,
            'approver_id': managers[0].id,
        })
        self.write({'approval_id': approval.id, 'state': 'submitted'})
        self.message_post(body=_(
            "Approbation demandée à %(approver)s.", approver=managers[0].name))

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_generate_po(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_("Seule une demande approuvée peut générer un bon de commande."))
        if not self.vendor_id:
            raise UserError(_("Renseignez le fournisseur avant de générer le bon de commande."))
        order = self.env['purchase.order'].create({
            'partner_id': self.vendor_id.id,
            'origin': self.name,
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.display_name,
                'product_qty': line.quantity,
                'price_unit': line.estimated_unit_cost,
            }) for line in self.line_ids],
        })
        self.write({'purchase_order_id': order.id, 'state': 'ordered'})
        self.message_post(body=_(
            "Bon de commande %(name)s généré.", name=order.name))
        return {
            'type': 'ir.actions.act_window',
            'name': order.name,
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': order.id,
        }


class ItamPurchaseRequestLine(models.Model):
    _name = 'itam.purchase.request.line'
    _description = "Ligne de demande d'achat"

    request_id = fields.Many2one('itam.purchase.request', string="Demande", required=True,
                                  ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string="Produit", required=True)
    description = fields.Char(string="Description",
                               help="Remplace le nom du produit sur le bon de commande si renseigné.")
    quantity = fields.Float(string="Quantité", default=1.0, required=True)
    estimated_unit_cost = fields.Float(string="Coût unitaire estimé")
    subtotal = fields.Float(string="Sous-total", compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'estimated_unit_cost')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.estimated_unit_cost
