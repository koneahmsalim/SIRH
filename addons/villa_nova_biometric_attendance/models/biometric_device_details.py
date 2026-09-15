import logging
from datetime import datetime, time as dtime

import pytz
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .zk_machine_attendance import DEVICE_TZ

_logger = logging.getLogger(__name__)


class BiometricDeviceDetails(models.Model):
    _inherit = 'biometric.device.details'

    # Etat de la liaison, tenu a jour a chaque synchronisation (toutes les 3
    # minutes). Sans cette trace, la seule facon de savoir si le boitier repond
    # serait de l'interroger - une vingtaine de secondes pendant lesquelles le
    # lecteur d'empreinte repond mal. Inenvisageable au chargement d'un ecran.
    x_derniere_liaison_ok = fields.Datetime(
        string="Dernière liaison réussie", readonly=True, copy=False,
        help="Horodatage de la dernière connexion aboutie au boîtier.",
    )
    x_injoignable_depuis = fields.Datetime(
        string="Injoignable depuis", readonly=True, copy=False,
        help="Renseigné dès qu'une connexion échoue, remis à vide au premier "
             "succès suivant. Permet de distinguer une absence réelle d'une "
             "absence de données.",
    )

    def _villa_nova_noter_liaison(self, reussie):
        """Consigne le resultat de la tentative de connexion."""
        self.ensure_one()
        maintenant = fields.Datetime.now()
        if reussie:
            valeurs = {'x_derniere_liaison_ok': maintenant}
            if self.x_injoignable_depuis:
                valeurs['x_injoignable_depuis'] = False
                _logger.info("Villa Nova biometrie : liaison retablie avec %s", self.device_ip)
            self.sudo().write(valeurs)
        elif not self.x_injoignable_depuis:
            # On horodate le DEBUT de la coupure, pas chaque echec : c'est
            # l'anciennete de la panne qui interesse, pas le dernier essai.
            self.sudo().write({'x_injoignable_depuis': maintenant})

    def action_clear_attendance(self):
        """Neutralise l'effacement total du journal de pointage.

        La methode d'origine enchaine deux destructions irreversibles :
        conn.clear_attendance() vide la memoire du boitier PHYSIQUE, puis un
        DELETE FROM zk_machine_attendance supprime tous les pointages bruts en
        base. Elle etait declenchee par un bouton "Clear Data" sans confirmation.

        Le 10/09/2026 a 09:02:35, un clic a detruit 3101 pointages et les
        badgeages du matin non encore synchronises : cinq salaries presents ont
        ete comptes absents, leurs heures d'arrivee introuvables (aucune
        sauvegarde, archivage WAL desactive, et l'autovacuum PostgreSQL avait
        recycle les lignes supprimees moins d'une minute plus tard).

        Le bouton est retire de la vue, mais la methode reste appelable par
        d'autres chemins (RPC, action serveur, vue heritee ailleurs) : on la
        bloque donc ici, a la source.
        """
        raise UserError(_(
            "L'effacement du journal de pointage est désactivé.\n\n"
            "Cette action vide à la fois la mémoire du boîtier et l'ensemble des "
            "pointages bruts enregistrés, sans possibilité de retour en arrière — y "
            "compris les badgeages du jour pas encore synchronisés, dont les salariés "
            "concernés se retrouvent comptés absents.\n\n"
            "Si la mémoire du boîtier doit réellement être libérée, faites-le depuis "
            "le boîtier lui-même, après avoir vérifié qu'une synchronisation vient "
            "d'aboutir."
        ))

    def action_villa_nova_sync_recent_attendance(self):
        for device in self:
            device._villa_nova_sync_recent_attendance()

    def _cron_villa_nova_sync_attendance(self):
        self.search([]).action_villa_nova_sync_recent_attendance()

    @api.model
    def _cron_villa_nova_controle_presences(self):
        """Garantit qu'un salarie ayant badge ne soit jamais compte absent.

        La chaine boitier -> pointage brut -> presence peut se rompre en
        silence a trois endroits, et dans les trois cas le salarie apparait
        "absent" alors qu'il a bien badge :

        1. le boitier est injoignable : la synchronisation renonce en ne
           laissant qu'un avertissement dans les journaux, que personne ne lit ;
        2. le pointage arrive mais n'est rattachable a aucun salarie
           (device_id_num absent, errone, ou salarie cree apres l'enrolement) ;
        3. le pointage est bien enregistre mais la reconstruction de la
           presence echoue pour ce salarie (elle est volontairement isolee dans
           un savepoint pour ne pas faire tomber toute la synchronisation).

        Ce controle rapproche donc les trois niveaux, REPARE ce qui peut l'etre
        automatiquement (cas 3, dont les causes sont souvent transitoires), et
        n'alerte que sur ce qui resiste.
        """
        from zk import ZK

        Employee = self.env['hr.employee']
        MachineAttendance = self.env['zk.machine.attendance']
        Attendance = self.env['hr.attendance']

        maintenant = DEVICE_TZ.localize(fields.Datetime.now())
        # Hors plage de presence, le controle n'aurait rien a constater et
        # solliciterait le boitier pour rien - chaque interrogation dure une
        # vingtaine de secondes pendant lesquelles le lecteur d'empreinte
        # repond mal.
        if not 6 <= maintenant.hour <= 20:
            return

        aujourdhui = maintenant.date()
        debut = DEVICE_TZ.localize(
            datetime.combine(aujourdhui, dtime.min)
        ).astimezone(pytz.utc).replace(tzinfo=None)
        fin = DEVICE_TZ.localize(
            datetime.combine(aujourdhui, dtime.max)
        ).astimezone(pytz.utc).replace(tzinfo=None)

        anomalies = {'injoignable': [], 'non_rattache': [], 'sans_presence': [], 'repares': []}

        # --- Niveau 1 : le boitier repond-il, et que dit-il ? -----------------
        ids_boitier_du_jour = set()
        for device in self.search([]):
            zk = ZK(device.device_ip, port=device.port_number or 4370, timeout=15,
                    password=int(device.device_password or 0), force_udp=False,
                    ommit_ping=False)
            conn = None
            try:
                conn = zk.connect()
                for p in conn.get_attendance():
                    if p.timestamp.date() == aujourdhui:
                        ids_boitier_du_jour.add(str(p.user_id))
                device._villa_nova_noter_liaison(True)
            except Exception:
                anomalies['injoignable'].append(device.display_name)
                device._villa_nova_noter_liaison(False)
                _logger.exception("Controle presences : boitier %s injoignable", device.device_ip)
            finally:
                if conn:
                    conn.disconnect()

        # --- Niveau 2 : des pointages sans salarie correspondant ? -----------
        for user_id in sorted(ids_boitier_du_jour):
            if not Employee.search_count([('device_id_num', '=', user_id)]):
                anomalies['non_rattache'].append(user_id)

        # --- Niveau 3 : pointage enregistre mais aucune presence construite --
        avec_pointage = MachineAttendance.search([
            ('punching_time', '>=', debut), ('punching_time', '<=', fin),
        ]).employee_id
        for employe in avec_pointage.browse(set(avec_pointage.ids)):
            if Attendance.search_count([
                ('employee_id', '=', employe.id),
                ('check_in', '>=', debut), ('check_in', '<=', fin),
            ]):
                continue
            # Nouvelle tentative : l'echec initial vient souvent d'une donnee
            # transitoire (presence orpheline, contrainte d'unicite) qui a pu
            # disparaitre depuis.
            try:
                with self.env.cr.savepoint():
                    employe._villa_nova_rebuild_attendance_from_punches()
            except Exception:
                _logger.exception(
                    "Controle presences : reconstruction toujours en echec pour %s", employe.name)
            if Attendance.search_count([
                ('employee_id', '=', employe.id),
                ('check_in', '>=', debut), ('check_in', '<=', fin),
            ]):
                anomalies['repares'].append(employe.name)
            else:
                anomalies['sans_presence'].append(employe.name)

        if anomalies['repares']:
            _logger.info("Controle presences : %s presence(s) reconstruite(s) automatiquement",
                         len(anomalies['repares']))
        if not any(anomalies[c] for c in ('injoignable', 'non_rattache', 'sans_presence')):
            return

        self._villa_nova_notifier_anomalies_presences(anomalies)

    @api.model
    def _villa_nova_notifier_anomalies_presences(self, anomalies):
        """Previent l'informatique ET les RH : la cause est technique, mais la
        consequence (un present compte absent) se traite cote RH."""
        destinataires = self.env['res.partner']
        for xmlid in ('villa_nova_itsm.group_itsm_manager', 'hr.group_hr_manager'):
            groupe = self.env.ref(xmlid, raise_if_not_found=False)
            if groupe:
                destinataires |= groupe.users.partner_id
        if not destinataires:
            return

        sections = []
        if anomalies['injoignable']:
            sections.append(Markup(
                "<p><b>Boîtier injoignable :</b> %s.<br/>"
                "Aucun pointage ne remonte tant que la liaison n'est pas rétablie ; "
                "les salariés présents apparaîtront absents.</p>"
            ) % ', '.join(anomalies['injoignable']))
        if anomalies['non_rattache']:
            # Formulation explicite : ecrire "identifiants : 0" laissait lire un
            # compte a zero, donc "aucun probleme", alors que 0 etait justement
            # le NUMERO du badge fautif. Le nombre et les numeros sont desormais
            # distincts et nommes.
            numeros = Markup(', ').join(
                Markup('<b>n° %s</b>') % uid for uid in anomalies['non_rattache'])
            sections.append(Markup(
                "<p><b>%(nb)s badge(s) ont pointé sans correspondre à aucun salarié.</b><br/>"
                "Numéro(s) relevé(s) sur le boîtier : %(numeros)s.<br/>"
                "Tant qu'aucun salarié ne porte ce numéro dans sa fiche, ces "
                "pointages sont ignorés. S'il s'agit d'une empreinte mal enrôlée "
                "ou d'un doigt inconnu, c'est à corriger sur le boîtier.</p>"
            ) % {'nb': len(anomalies['non_rattache']), 'numeros': numeros})
        if anomalies['sans_presence']:
            sections.append(Markup(
                "<p><b>Ont badgé mais ne sont pas comptés présents :</b><ul>%s</ul>"
                "La reconstruction automatique a été retentée sans succès pour ces "
                "salariés : leur présence est à saisir manuellement.</p>"
            ) % Markup('').join(Markup('<li>%s</li>') % n for n in anomalies['sans_presence']))
        if anomalies['repares']:
            sections.append(Markup(
                "<p><i>Pour information, %d présence(s) ont été reconstruites "
                "automatiquement, aucune action n'est requise.</i></p>"
            ) % len(anomalies['repares']))

        self.env['mail.thread'].sudo().message_notify(
            partner_ids=destinataires.ids,
            subject="Contrôle des pointages : anomalie détectée",
            body=Markup("<p>Le contrôle de cohérence des pointages a relevé ceci :</p>%s") %
            Markup('').join(sections),
        )

    def _villa_nova_sync_recent_attendance(self):
        """Importe uniquement les pointages posterieurs au dernier deja
        connu, au lieu de reparcourir tout l'historique du boitier (des
        dizaines de milliers d'enregistrements, beaucoup trop lent pour un
        rafraichissement frequent)."""
        self.ensure_one()
        from zk import ZK

        MachineAttendance = self.env['zk.machine.attendance']
        Employee = self.env['hr.employee']

        last = MachineAttendance.search([], order='punching_time desc', limit=1)
        since = last.punching_time if last else datetime(2000, 1, 1)

        zk = ZK(self.device_ip, port=self.port_number or 4370, timeout=15,
                password=int(self.device_password or 0), force_udp=False, ommit_ping=False)
        try:
            conn = zk.connect()
        except Exception:
            _logger.warning("Villa Nova biometrie : connexion au boitier %s impossible", self.device_ip)
            self._villa_nova_noter_liaison(False)
            return
        self._villa_nova_noter_liaison(True)

        try:
            punches = conn.get_attendance()
        finally:
            conn.disconnect()

        new_punches = [p for p in punches if p.timestamp > since]
        if not new_punches:
            return

        created = 0
        for each in sorted(new_punches, key=lambda p: p.timestamp):
            local_dt = DEVICE_TZ.localize(each.timestamp)
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)

            employee = Employee.search([
                ('device_id_num', '=', each.user_id),
                ('company_id', '=', self.company_id.id or self.env.company.id),
            ], limit=1)
            if not employee:
                continue

            duplicate = MachineAttendance.search([
                ('device_id_num', '=', each.user_id),
                ('punching_time', '=', utc_dt),
                ('company_id', '=', employee.company_id.id),
            ], limit=1)
            if duplicate:
                continue

            MachineAttendance.create({
                'employee_id': employee.id,
                'device_id_num': each.user_id,
                'attendance_type': str(each.status),
                'punch_type': str(each.punch),
                'punching_time': utc_dt,
                'address_id': self.address_id.id,
                'company_id': employee.company_id.id,
            })
            created += 1

        _logger.info(
            "Villa Nova biometrie : %s nouveaux pointages importes depuis le boitier %s",
            created, self.device_ip,
        )
