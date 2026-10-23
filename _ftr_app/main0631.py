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
    extra=get('_ftr_extraordinarias.json')
    if extra.get('version')!=1 or not isinstance(extra.get('pending'),dict) or not isinstance(extra.get('history'),list):
        raise ValueError('No se pudo verificar la programación extraordinaria publicada.')
    from _ftr_runtime.oneoff import recover_interrupted
    recover_interrupted(extra,agenda_bridge.datetime.now(agenda_bridge.timezone.utc))
    from _ftr_runtime import dictionary_rules as rules
    dictionary=rules.validate(get('_ftr_diccionario.json'))
    result = dict(config=config, digest=digest(config), state=state, revision=revision,oneoffs=extra,
                  dictionary_digest=rules.digest(dictionary))
    write_json(server.DATA/'config_remota.json', result)
    return result


def pending_runs(since):
    from _ftr_app.queue_runs import scan
    return scan(server.api,since,agenda_bridge.classify_run)


def dispatch(row):
    if row['action'] in ('dictionary-save','history-import','history-review','history-recalculate'):
        from _ftr_runtime.statistics_commands import clean, WORKFLOW
        payload=clean(row['action'],row['statistical'])
        server.api('POST','actions/workflows/'+WORKFLOW+'/dispatches',{'ref':'main','inputs':{'action':row['action'],'command_json':json.dumps(payload),'expected':row['expected'],'request_id':row['id']}})
        return
    payload=encoded(row['config']).decode() if row['config'] else ''
    if row['action'] in ('oneoff-set','oneoff-cancel'):payload=json.dumps(row['oneoff'])
    elif row['action'] in ('drive','cnrt','all'):payload=json.dumps(dict(requested_utc=row['created_at']))
    server.api('POST', 'actions/workflows/' + server.WORKFLOW + '/dispatches', {
        'ref': 'main', 'inputs': dict(action=row['action'],
            config_json=payload,
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
    from _ftr_runtime import schedule_health
    result['schedule_health']=schedule_health.inspect(result['config'],result['oneoffs'],result['revision'],lambda path:server.api('GET',path))
    result['runs'] = agenda_bridge.last_runs()
    result['schedule'] = agenda_bridge.describe(result['config'], result['state'], agenda_bridge.datetime.now(agenda_bridge.timezone.utc))
    result['outbox'] = outbox.status()
    return server.jsonify(result)


def install():
    agenda_bridge.install()
    from _ftr_app.version import VERSION
    server.VERSION = VERSION
    from _ftr_app.statistics_admin import install as install_statistics
    install_statistics(server)
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
    def check():
        return server.jsonify(outbox.check(server.request.get_json().get('request_id')))
    def resolve():
        data=server.request.get_json()
        return server.jsonify(outbox.resolve(data.get('request_id'),data.get('confirmation')))
    def resume():
        return server.jsonify(outbox.resume(server.request.get_json().get('confirmation')))
    server.app.add_url_rule('/api/orders/check', 'check_order', check, methods=['POST'])
    server.app.add_url_rule('/api/orders/resolve', 'resolve_order', resolve, methods=['POST'])
    server.app.add_url_rule('/api/orders/resume', 'resume_orders', resume, methods=['POST'])


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
