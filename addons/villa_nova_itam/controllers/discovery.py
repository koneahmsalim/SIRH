import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

DISCOVERY_SCOPE = 'itam_discovery'


class ItamDiscoveryController(http.Controller):
    """Point d'entree reel pour un agent de decouverte externe (script,
    RMM, MDM...) - pas un scanner reseau simule : authentification par cle
    API native Odoo (res.users.apikeys), un vrai script peut l'appeler des
    aujourd'hui. Voir itam_discovery.py pour la logique de rattachement/
    creation d'actif."""

    @http.route('/itam/discovery/report', type='http', auth='public', methods=['POST'], csrf=False)
    def report(self, **kwargs):
        api_key = request.httprequest.headers.get('X-Api-Key')
        if not api_key:
            return request.make_json_response({'error': 'missing_api_key'}, status=401)

        uid = request.env['res.users.apikeys'].sudo()._check_credentials(scope=DISCOVERY_SCOPE, key=api_key)
        if not uid:
            return request.make_json_response({'error': 'invalid_api_key'}, status=401)

        try:
            payload = json.loads(request.httprequest.data or b'{}')
        except ValueError:
            return request.make_json_response({'error': 'invalid_json'}, status=400)

        if not payload.get('serial_no') and not payload.get('hostname'):
            return request.make_json_response({'error': 'serial_no_or_hostname_required'}, status=400)

        request.update_env(user=uid)
        source_ip = request.httprequest.remote_addr
        try:
            equipment, result = request.env['maintenance.equipment']._itam_discovery_upsert(
                payload, source_ip=source_ip)
        except Exception:
            _logger.exception("villa_nova_itam : echec du traitement d'un rapport de decouverte")
            return request.make_json_response({'error': 'processing_failed'}, status=500)

        return request.make_json_response({
            'result': result,
            'equipment_id': equipment.id,
            'asset_tag': equipment.asset_tag,
        })
