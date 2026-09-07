import json
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EndpointAgentController(http.Controller):
    """API reelle pour l'agent Go (voir addons/villa_nova_endpoint/agent/) -
    connexion sortante uniquement (l'agent interroge le serveur, jamais
    l'inverse - Objectif 2 du brief RMM), authentification par identite
    dediee (jamais res.users.apikeys). Reutilise
    maintenance.equipment._itam_discovery_upsert (Phase 5) pour le
    find-or-create de l'actif a l'enrolement plutot que de dupliquer cette
    logique - integration inter-phases, meme raisonnement que
    itsm.change.action_cmdb_impact_preview."""

    def _read_json(self):
        try:
            return json.loads(request.httprequest.data or b'{}')
        except ValueError:
            return None

    @http.route('/endpoint/agent/enroll', type='http', auth='public', methods=['POST'], csrf=False)
    def enroll(self, **kwargs):
        payload = self._read_json()
        if payload is None:
            return request.make_json_response({'error': 'invalid_json'}, status=400)

        token = request.httprequest.headers.get('X-Enrollment-Key') or payload.get('enrollment_key')
        EnrollmentKey = request.env['itsm.endpoint.enrollment.key'].sudo()
        key = EnrollmentKey._find_valid(token)
        if not key:
            return request.make_json_response({'error': 'invalid_or_expired_enrollment_key'}, status=401)

        if not payload.get('serial_no') and not payload.get('hostname'):
            return request.make_json_response({'error': 'serial_no_or_hostname_required'}, status=400)

        Equipment = request.env['maintenance.equipment'].sudo()
        source_ip = request.httprequest.remote_addr
        try:
            equipment, _result = Equipment._itam_discovery_upsert(payload, source_ip=source_ip)
            agent, secret = request.env['itsm.endpoint.agent']._enroll(
                equipment, key,
                platform=payload.get('platform'),
                agent_version=payload.get('agent_version'),
            )
            equipment._endpoint_apply_inventory(payload)
            agent.write({'last_checkin': agent.enrolled_date, 'checkin_count': 1})
        except Exception:
            _logger.exception("villa_nova_endpoint : échec de l'enrôlement d'un agent")
            return request.make_json_response({'error': 'enrollment_failed'}, status=500)

        return request.make_json_response({
            'agent_id': agent.agent_uuid,
            'agent_secret': secret,
            'equipment_id': equipment.id,
            'checkin_interval_seconds': 900,
        })

    @http.route('/endpoint/agent/checkin', type='http', auth='public', methods=['POST'], csrf=False)
    def checkin(self, **kwargs):
        agent_id = request.httprequest.headers.get('X-Agent-Id')
        agent_secret = request.httprequest.headers.get('X-Agent-Secret')
        agent = request.env['itsm.endpoint.agent']._authenticate(agent_id, agent_secret)
        if not agent:
            return request.make_json_response({'error': 'invalid_credentials'}, status=401)

        payload = self._read_json()
        if payload is None:
            return request.make_json_response({'error': 'invalid_json'}, status=400)

        try:
            agent.equipment_id.sudo()._endpoint_apply_inventory(payload)
            agent.sudo().write({
                'last_checkin': fields.Datetime.now(),
                'checkin_count': agent.checkin_count + 1,
                'agent_version': payload.get('agent_version') or agent.agent_version,
            })
        except Exception:
            _logger.exception("villa_nova_endpoint : échec du check-in de l'agent %s", agent.agent_uuid)
            return request.make_json_response({'error': 'checkin_failed'}, status=500)

        return request.make_json_response({
            'status': 'ok',
            'checkin_interval_seconds': 900,
            # Liste volontairement vide : le protocole de check-in est concu
            # pour porter des commandes en attente des la Phase "Actions a
            # distance" (roadmap RMM, objectif 4) SANS changer de contrat
            # d'API - mais aucune execution de commande n'est implementee
            # dans cette phase (contrainte explicite de l'utilisateur : pas
            # d'execution arbitraire non controlee).
            'commands': [],
        })
