"""Continuación 06.3: solo transmite órdenes expresamente confirmadas.

No instala servicios, no activa LocalClock y no dispara horarios desde la PC.
"""
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
from _ftr_app.outbox import Outbox, AuthorizationError
from _ftr_app.local_clock import write_json
from _ftr_runtime.config import clean_config, digest, encoded


def snapshot():
    # Configuración y estado pertenecen a una misma revisión.
    revision = server.api('GET', 'git/ref/heads/main')['object']['sha']
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('GitHub no devolvió una revisión válida.')
    def get(name):
        value = server.api('GET', 'contents/' + name + '?ref=' + revision)
        return json.loads(base64.b64decode(value['content']))
    config = clean_config(get('_ftr_config.json'))
    state = get('_ftr_estado.json')
    if not isinstance(state, dict):
        raise ValueError('No se pudo interpretar el estado publicado.')
    result = dict(config=config, digest=digest(config), state=state, revision=revision)
    write_json(server.DATA/'config_remota.json', result)
    return result


def pending_runs(since):
    found = {}
    for workflow in (server.WORKFLOW, 'actualizar_parques.yml'):
        # El rango limita consultas y permite recuperar más de seis ejecuciones.
        for page in range(1, 4):
            rows = server.api('GET', 'actions/workflows/' + workflow +
                              '/runs?branch=main&per_page=100&page=' + str(page)).get('workflow_runs', [])
            for row in rows:
                title = row.get('display_title', '')
                identifier = title.rsplit(' · ', 1)[-1]
                result = dict(id=row['id'], status=row['status'], conclusion=row.get('conclusion'),
                              request_id=identifier, url=row.get('html_url'))
                if row['status'] == 'completed' and re.fullmatch('[0-9a-f]{32}', identifier):
                    key = (row['id'], row.get('run_attempt', 1), row.get('updated_at'), row['status'], row.get('conclusion'))
                    if key not in agenda_bridge._cache:
                        jobs = server.api('GET', f"actions/runs/{row['id']}/jobs?per_page=100").get('jobs', [])
                        if len(agenda_bridge._cache) >= 100:
                            agenda_bridge._cache.clear()
                        agenda_bridge._cache[key] = agenda_bridge.classify_run(row, jobs)
                    result.update(agenda_bridge._cache[key])
                found[row['id']] = result
            if len(rows) < 100 or rows[-1]['created_at'] < since:
                break
    return list(found.values())


def dispatch(row):
    server.api('POST', 'actions/workflows/' + server.WORKFLOW + '/dispatches', {
        'ref': 'main', 'inputs': dict(action=row['action'],
            config_json=encoded(row['config']).decode() if row['config'] else '',
            expected=row['expected'], request_id=row['id'])})


outbox = Outbox(lambda: server.DATA, snapshot, pending_runs, dispatch)


def submit():
    data = server.request.get_json()
    if not isinstance(data, dict):
        raise ValueError('La solicitud no es válida.')
    published = server.cached('config_remota.json', None)
    if published is None and not data.get('expected'):
        published = snapshot()
    row = outbox.enqueue(data, published)
    # Responde al guardado local; el hilo de salida confirma el envío después.
    return server.jsonify(ok=True, request_id=row['id'], queued=True,
                          message='Pendiente de envío. La orden está guardada en esta computadora.', order=row)


def status():
    result = snapshot()
    result['runs'] = agenda_bridge.last_runs()
    result['schedule'] = agenda_bridge.describe(result['config'], result['state'], agenda_bridge.datetime.now(agenda_bridge.timezone.utc))
    result['outbox'] = outbox.status()
    return server.jsonify(result)


def install():
    agenda_bridge.install()
    server.VERSION = '06.3.1'
    server.app.view_functions['submit'] = submit
    server.app.view_functions['status'] = status
    original_connect = server.app.view_functions['connect']
    def connect():
        result = original_connect()
        outbox.reconnected()
        return result
    server.app.view_functions['connect'] = connect
    server.app.add_url_rule('/api/orders', 'orders', lambda: server.jsonify(outbox.status()), methods=['GET'])
    def cancel():
        return server.jsonify(outbox.cancel(server.request.get_json().get('request_id')))
    server.app.add_url_rule('/api/orders/cancel', 'cancel_order', cancel, methods=['POST'])


def main():
    install()
    testing = '--self-test' in sys.argv or '--browser-test' in sys.argv
    original_verify = server.verify_local_http
    def verify():
        original_verify()
        if not testing:
            outbox.start()
    server.verify_local_http = verify
    try:
        server.main()
    finally:
        outbox.stop()


if __name__ == '__main__':
    main()
