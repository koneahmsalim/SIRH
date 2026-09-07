import logging
import re
import subprocess
import xml.etree.ElementTree as ET

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# CIDR/plage IPv4 uniquement - valide AVANT de construire la commande nmap,
# jamais une chaine libre passee telle quelle (meme si subprocess.run avec
# une liste d'arguments empeche deja l'injection shell classique, une chaine
# du type "--script=..." pourrait etre interpretee comme une option nmap
# plutot qu'une cible si on ne validait pas le format).
SUBNET_RE = re.compile(r'^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$')
SCAN_TIMEOUT_SECONDS = 120

STATE_SELECTION = [
    ('draft', "Brouillon"),
    ('running', "En cours"),
    ('completed', "Terminé"),
    ('failed', "Échoué"),
]


class ItamDiscoveryScan(models.Model):
    """Scan reseau leger (ping sweep nmap -sn) execute en synchrone depuis un
    cron/bouton - PAS un service toujours actif separe : a l'echelle d'un
    site/VLAN, un scan de quelques dizaines de secondes declenche a la
    demande ou une fois par jour suffit largement, meme raisonnement que les
    autres cron de ce projet (SLA, garanties, licences). Necessite que le
    conteneur Odoo ait une route reseau vers le sous-reseau cible - dans un
    deploiement reel, ca implique un agent de decouverte sur le LAN concerne
    ou un Odoo deploye sur site, pas necessairement le serveur central si le
    LAN scanne est distant (voir limite documentee dans le README du
    module)."""
    _name = 'itam.discovery.scan'
    _description = "Scan de découverte réseau"
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(string="Référence", default="Nouveau", copy=False, readonly=True)
    subnet = fields.Char(string="Sous-réseau (CIDR)", required=True,
                          help="Ex. 192.168.1.0/24 - IPv4/CIDR uniquement.")
    state = fields.Selection(STATE_SELECTION, string="Statut", default='draft',
                              required=True, tracking=True, index=True)
    requested_by = fields.Many2one('res.users', string="Demandé par", default=lambda self: self.env.user)
    started_date = fields.Datetime(string="Démarré le", readonly=True)
    finished_date = fields.Datetime(string="Terminé le", readonly=True)

    device_ids = fields.One2many('itam.discovery.device', 'scan_id', string="Appareils détectés")
    device_count = fields.Integer(string="Appareils détectés", compute='_compute_device_count')
    new_device_count = fields.Integer(string="Non rapprochés", compute='_compute_device_count')
    error_message = fields.Text(string="Erreur", readonly=True)
    raw_output = fields.Text(string="Sortie brute (débogage)", readonly=True)

    @api.depends('device_ids', 'device_ids.matched_equipment_id')
    def _compute_device_count(self):
        for scan in self:
            scan.device_count = len(scan.device_ids)
            scan.new_device_count = len(scan.device_ids.filtered(lambda d: not d.matched_equipment_id))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('itam.discovery.scan') or 'Nouveau'
        return super().create(vals_list)

    def action_run_scan(self):
        for scan in self:
            scan._run_one()

    def _run_one(self):
        self.ensure_one()
        if not SUBNET_RE.match(self.subnet or ''):
            raise UserError(_(
                "Sous-réseau invalide : %(subnet)s - format attendu \"192.168.1.0/24\" ou une IP unique.",
                subnet=self.subnet))

        self.write({'state': 'running', 'started_date': fields.Datetime.now(), 'error_message': False})
        self.env.cr.commit()  # visible immediatement meme si le scan prend du temps

        try:
            result = subprocess.run(
                ['nmap', '-sn', '-oX', '-', '--', self.subnet],
                capture_output=True, timeout=SCAN_TIMEOUT_SECONDS, text=True,
            )
        except FileNotFoundError:
            self._fail(_("nmap n'est pas installé dans ce conteneur."))
            return
        except subprocess.TimeoutExpired:
            self._fail(_("Le scan a dépassé le délai de %(s)ds.", s=SCAN_TIMEOUT_SECONDS))
            return

        if result.returncode != 0:
            self._fail(_("nmap a échoué (code %(code)s) : %(err)s",
                          code=result.returncode, err=(result.stderr or '')[:2000]))
            return

        try:
            devices = self._parse_nmap_xml(result.stdout)
        except ET.ParseError as e:
            self._fail(_("Sortie nmap illisible : %(err)s", err=str(e)))
            return

        self.device_ids.unlink()
        Device = self.env['itam.discovery.device']
        for device in devices:
            Device.create({
                'scan_id': self.id,
                'ip_address': device['ip'],
                'mac_address': device['mac'],
                'hostname': device['hostname'],
            })

        self.write({
            'state': 'completed', 'finished_date': fields.Datetime.now(),
            'raw_output': result.stdout[:20000],
        })
        self.env.cr.commit()

    def _fail(self, message):
        self.write({'state': 'failed', 'finished_date': fields.Datetime.now(), 'error_message': message})
        self.env.cr.commit()
        _logger.warning("villa_nova_endpoint : scan de découverte %s échoué : %s", self.name, message)

    def action_reset_draft(self):
        self.write({'state': 'draft', 'error_message': False})

    @staticmethod
    def _parse_nmap_xml(xml_text):
        root = ET.fromstring(xml_text)
        devices = []
        for host in root.findall('host'):
            status = host.find('status')
            if status is None or status.get('state') != 'up':
                continue
            ip = mac = hostname = None
            for addr in host.findall('address'):
                addrtype = addr.get('addrtype')
                if addrtype == 'ipv4':
                    ip = addr.get('addr')
                elif addrtype == 'mac':
                    mac = addr.get('addr')
            hostnames_el = host.find('hostnames')
            if hostnames_el is not None:
                name_el = hostnames_el.find('hostname')
                if name_el is not None:
                    hostname = name_el.get('name')
            if ip:
                devices.append({'ip': ip, 'mac': mac, 'hostname': hostname})
        return devices
