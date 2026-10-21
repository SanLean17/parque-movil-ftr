"""Entrada 06.4. Respaldo local OPCIONAL, desactivado hasta confirmación."""
from __future__ import annotations
import base64
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server
import agenda_bridge
from local_clock import LocalClock
from _ftr_runtime.config import clean_config


def snapshot():
    # Configuración y estado de la misma revisión, nunca un borrador local.
    ref = server.api('GET', 'git/ref/heads/main')['object']['sha']
    if not re.fullmatch('[0-9a-f]{40}', ref):
        raise ValueError('GitHub no devolvió una revisión válida.')
    def get(name):
        data = server.api('GET', 'contents/'+name+'?ref='+ref)
        return json.loads(base64.b64decode(data['content']))
    config = clean_config(get('_ftr_config.json'))
    state = get('_ftr_estado.json')
    if not isinstance(state, dict):
        raise ValueError('El estado publicado no es válido.')
    return config, state, ref


def active_runs():
    found = {}
    for workflow in (server.WORKFLOW, 'actualizar_parques.yml'):
        for row in server.api('GET', 'actions/workflows/'+workflow+'/runs?branch=main&per_page=30').get('workflow_runs', []):
            found[row['id']] = row
    return list(found.values())


def dispatch(identifier):
    # NO all: CNRT conserva sus cinco días; fuentes deshabilitadas se omiten.
    server.api('POST', 'actions/workflows/'+server.WORKFLOW+'/dispatches', {
        'ref': 'main', 'inputs': {'action': 'scheduled', 'config_json': '',
                                'expected': '', 'request_id': identifier}})


clock = LocalClock(lambda: server.DATA, snapshot, active_runs, dispatch, server._lock)


def install():
    agenda_bridge.install()
    server.VERSION = '06.4'
    original_index = server.app.view_functions['index']
    def index():
        html = original_index()
        return html.replace('</body>', '<script src="/local-clock-ui.js"></script></body>')
    server.app.view_functions['index'] = index
    server.app.add_url_rule('/local-clock-ui.js', 'local_clock_script', lambda: server.app.response_class(
        (Path(getattr(sys, '_MEIPASS', str(Path(__file__).parent)))/'local_clock_ui.js').read_text(encoding='utf-8'), mimetype='text/javascript'))
    server.app.add_url_rule('/api/local-clock', 'local_clock_status', lambda: server.jsonify(clock.status()), methods=['GET'])
    def settings():
        data = server.request.get_json()
        value = data.get('enabled') if isinstance(data, dict) else None
        if type(value) is not bool:
            raise ValueError('Elegí activar o desactivar el respaldo de esta PC.')
        if value:
            server.token()
            info = server.api('GET', 'actions/workflows/'+server.WORKFLOW)
            if info.get('state') != 'active':
                raise ValueError('El sincronizador de GitHub no está habilitado. No se activó el respaldo.')
        return server.jsonify(clock.set_enabled(value))
    server.app.add_url_rule('/api/local-clock', 'local_clock_settings', settings, methods=['POST'])


def main():
    install()
    testing = '--self-test' in sys.argv or '--browser-test' in sys.argv
    original_verify = server.verify_local_http
    def verify():
        original_verify()
        if not testing:
            clock.start()
    server.verify_local_http = verify
    try:
        server.main()
    finally:
        clock.stop()


if __name__ == '__main__':
    main()
