from odoo import _, api, models


class ItsmContract(models.Model):
    """Rappels de renouvellement - meme mecanisme de deduplication par
    substring de resume que l'escalade SLA (Phase 3) : une seule activite
    par transition, pas de spam a chaque passage du cron tant que le
    contrat reste dans le meme etat."""
    _inherit = 'itsm.contract'

    def _escalate_renewal(self):
        self.ensure_one()
        if not self.responsible_id:
            return
        summary = _("Renouvellement à prévoir : %(name)s", name=self.name)
        already_notified = self.activity_ids.filtered(
            lambda a: a.user_id == self.responsible_id and self.name in (a.summary or ''))
        if already_notified:
            return
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.responsible_id.id,
            summary=summary,
            note=_(
                "Le contrat <b>%(name)s</b> (%(vendor)s) %(status)s le %(date)s.",
                name=self.name, vendor=self.vendor_id.name,
                status=_("a expiré") if self.renewal_status == 'expired' else _("expire"),
                date=self.end_date,
            ),
        )

    @api.model
    def _cron_check_contract_renewals(self):
        contracts = self.search([('renewal_status', 'in', ('expiring_soon', 'expired')), ('active', '=', True)])
        for contract in contracts:
            contract._escalate_renewal()
        self.env.cr.commit()


class MaintenanceEquipment(models.Model):
    """Meme logique de rappel pour les garanties materielles - cible les
    gestionnaires ITAM (pas de responsable individuel sur un actif,
    contrairement au contrat) plutot que de forcer l'ajout d'un champ
    "responsable" sur chaque actif."""
    _inherit = 'maintenance.equipment'

    def _escalate_warranty(self, notify_users):
        self.ensure_one()
        for user in notify_users:
            already_notified = self.activity_ids.filtered(
                lambda a: a.user_id == user and 'garantie' in (a.summary or '').lower())
            if already_notified:
                continue
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=_("Garantie à surveiller : %(name)s", name=self.name),
                note=_(
                    "La garantie de <b>%(name)s</b> (%(tag)s) %(status)s le %(date)s.",
                    name=self.name, tag=self.asset_tag or '',
                    status=_("a expiré") if self.warranty_status == 'expired' else _("expire"),
                    date=self.warranty_date,
                ),
            )

    @api.model
    def _cron_check_warranty_renewals(self):
        # Filtre sur email renseigne : group_itam_manager inclut aussi le
        # compte technique de l'agent de decouverte (Phase 5, API uniquement,
        # jamais de connexion interactive) - une activite "a faire" qui
        # atterrit dessus ne serait jamais vue par personne.
        managers = self.env.ref('villa_nova_itam.group_itam_manager').users.filtered('email')
        if not managers:
            return
        equipments = self.search([('warranty_status', 'in', ('expiring_soon', 'expired'))])
        for equipment in equipments:
            equipment._escalate_warranty(managers)
        self.env.cr.commit()


class ItamSoftwareLicense(models.Model):
    # itam.software.license n'herite jusqu'ici que de mail.thread - ajoute
    # mail.activity.mixin ici (necessaire pour activity_schedule) plutot
    # que dans le module Phase 4 qui n'en avait pas besoin a l'epoque.
    _name = 'itam.software.license'
    _inherit = ['itam.software.license', 'mail.activity.mixin']

    def _escalate_license_renewal(self, notify_users):
        self.ensure_one()
        for user in notify_users:
            already_notified = self.activity_ids.filtered(
                lambda a: a.user_id == user and self.name in (a.summary or ''))
            if already_notified:
                continue
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=_("Licence à renouveler : %(name)s", name=self.name),
                note=_(
                    "La licence <b>%(name)s</b> %(status)s le %(date)s.",
                    name=self.name,
                    status=_("a expiré") if self.renewal_status == 'expired' else _("expire"),
                    date=self.expiration_date,
                ),
            )

    @api.model
    def _cron_check_license_renewals(self):
        managers = self.env.ref('villa_nova_itam.group_itam_manager').users.filtered('email')
        if not managers:
            return
        licenses = self.search([('renewal_status', 'in', ('expiring_soon', 'expired'))])
        for license in licenses:
            license._escalate_license_renewal(managers)
        self.env.cr.commit()
