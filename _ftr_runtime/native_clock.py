"""Reloj alojado en GitHub: espera sin runner y relee main al despertar.

No importa lectores, no escribe datos ni configura permisos/entornos. Cada
ejecución solicita directamente el próximo workflow_dispatch y termina. La prueba
termina tras cuatro esperas y nunca puede despachar el coordinador real.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import agenda, oneoff, publication_retry
from .config import load as load_config, digest

REPO = 'SanLean17/parque-movil-ftr'
CLOCK = 'ftr_reloj_nativo.yml'
REARM = 'ftr_rearmar_reloj.yml'
COORDINATOR = 'ftr_sincronizar.yml'
PRODUCTION = (COORDINATOR, 'actualizar_parques.yml', 'ftr_recuperar_turnos.yml', 'ftr_extraordinarias.yml')
MINUTES = (1, 5, 15, 60, 240, 720, 1440, 10080)
PREFIX = 'ftr-espera-'
TITLE = re.compile(r'^FTR · reloj · (real|prueba) · paso ([0-3]) · intento ([0-3])$')
ACTIVE = ('queued', 'in_progress', 'waiting', 'pending', 'requested')
BACKOFF = (0, 5, 15, 60)


def instant(value):
    return oneoff.instant(value).astimezone(timezone.utc)


def running_until(extra, source):
    row = extra.get('last_execution', {}).get(source, {})
    if row.get('status') == 'running' and row.get('started_utc'):
        return instant(row['started_utc']) + timedelta(minutes=95, seconds=1)
    return None


def next_work(config, state, extra, moment):
    """Siguiente comprobación útil; respeta la agenda y los plazos del worker."""
    if moment.tzinfo is None:
        raise ValueError('Se necesita una fecha con zona horaria.')
    candidates = []

    def add(at, kind, source=None):
        if source and (until := running_until(extra, source)) and until > moment:
            at = max(at, until)
        candidates.append(dict(at_utc=at.astimezone(timezone.utc).isoformat(), kind=kind, source=source))

    for key in ('drive', 'cnrt'):
        if not config[key]['enabled']:
            continue
        slot = agenda.eligible_slot(config, state, key, moment)
        pending = slot and not agenda.slot_satisfied(state, key, slot)
        at = agenda.slot_time(slot) if pending else agenda.next_slot_time(config, key, moment)
        row = state.get(key, {})
        row = row.get('recurrence', row)
        if pending and row.get('status') != 'success' and row.get('attempt_utc'):
            at = max(at, instant(row['attempt_utc']) + timedelta(hours=1))
        add(at, 'recurrent', key)
    for key, row in extra.get('pending', {}).items():
        add(instant(row['at']), 'oneoff', key)
    if publication_retry.pending(state):
        attempted = state.get('publication', {}).get('attempt_utc')
        add(max(moment, instant(attempted) + timedelta(minutes=15)) if attempted else moment,
            'publication')
    for row in [*extra.get('history', []), *extra.get('execution_history', []),
                *extra.get('last_execution', {}).values(), *extra.get('receipts', {}).values()]:
        if row.get('status') == 'running' and row.get('started_utc'):
            add(instant(row['started_utc']) + timedelta(minutes=95, seconds=1), 'interrupted')
    if not candidates:
        return None
    candidates.sort(key=lambda row: (row['at_utc'], row['kind'], row['source'] or ''))
    return dict(next_due_utc=candidates[0]['at_utc'], candidates=candidates, config_digest=digest(config))


def choose_wait(target, moment, retry=0):
    target = max(target, moment + timedelta(minutes=BACKOFF[retry]))
    remaining = max(1, int((target - moment).total_seconds() // 60))
    return max(value for value in MINUTES if value <= remaining)


def snapshot(root, moment):
    root = Path(root)
    config = load_config(root)
    state = json.loads((root / '_ftr_estado.json').read_text(encoding='utf-8-sig'))
    if not isinstance(state, dict):
        raise ValueError('No se pudo verificar el estado de las fuentes.')
    return next_work(config, state, oneoff.load(root), moment)


def api(method, path, payload=None):
    token = os.environ.get('GITHUB_TOKEN', '')
    if not token:
        raise ValueError('Falta la autorización temporal de GitHub Actions.')
    request = Request('https://api.github.com/repos/' + REPO + '/' + path,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                               'Content-Type': 'application/json', 'User-Agent': 'FTR-native-clock',
                               'X-GitHub-Api-Version': '2022-11-28'}, method=method)
    # Un POST ambiguo puede repetirse. La exclusión mutua y los turnos consumidos
    # del coordinador siguen impidiendo lecturas duplicadas.
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise ValueError('GitHub no confirmó la operación del reloj (HTTP ' + str(exc.code) + ').') from None
        except (URLError, TimeoutError, OSError):
            if attempt == 2:
                raise ValueError('No se pudo confirmar la conexión del reloj con GitHub.') from None
        time.sleep((2, 5)[attempt])


def workflow_active(call, name):
    return call('GET', 'actions/workflows/' + name).get('state') == 'active'


def validate_wait(call, minutes):
    if minutes not in MINUTES:
        raise ValueError('Espera fuera de los valores admitidos.')
    row = call('GET', 'environments/' + PREFIX + str(minutes))
    rules = row.get('protection_rules', [])
    timers = [rule for rule in rules if rule.get('type') == 'wait_timer']
    if len(timers) != 1 or timers[0].get('wait_timer') != minutes:
        raise ValueError('La espera de GitHub no coincide con la configurada. No se ejecutarán fuentes.')
    if any(rule.get('type') not in ('wait_timer', 'branch_policy') for rule in rules):
        raise ValueError('El entorno del reloj requiere una aprobación adicional y no es autónomo.')


def busy(call):
    # Filtrar por estado evita perder una ejecución larga entre las ya terminadas.
    for status in ('in_progress', 'queued', 'waiting', 'pending'):
        rows = call('GET', 'actions/runs?branch=main&status=' + status + '&per_page=100').get('workflow_runs', [])
        if any(row.get('path', '').split('@', 1)[0].rsplit('/', 1)[-1] in PRODUCTION for row in rows):
            return True
    return False


def dispatch(call, workflow, inputs):
    if workflow not in (CLOCK, COORDINATOR):
        raise ValueError('Destino de automatización no permitido.')
    call('POST', 'actions/workflows/' + workflow + '/dispatches', {'ref': 'main', 'inputs': inputs})


def cancel_waiters(call):
    rows = call('GET', 'actions/workflows/' + CLOCK + '/runs?branch=main&per_page=30').get('workflow_runs', [])
    for row in rows:
        match = TITLE.fullmatch(row.get('display_title', ''))
        if match and match[1] == 'real' and row.get('status') in ACTIVE:
            identifier = str(row.get('id', ''))
            if identifier.isdigit():
                call('POST', 'actions/runs/' + identifier + '/cancel')


def prepare(root, moment, mode, step, retry, enabled, call=api):
    if mode == 'real' and not enabled:
        return dict(armed=False, status='disabled', sources_read=[])
    if not workflow_active(call, CLOCK) or not workflow_active(call, REARM):
        raise ValueError('El reloj o su renovación están deshabilitados en GitHub.')
    plan = snapshot(root, moment) if mode == 'real' else {'next_due_utc': (moment + timedelta(minutes=1)).isoformat()}
    if plan is None:
        return dict(armed=False, status='idle', sources_read=[])
    target = instant(plan['next_due_utc'])
    if mode == 'real' and busy(call):
        # Los avisos workflow_run de ejecuciones iniciadas por GITHUB_TOKEN
        # pueden no llegar: volver a comprobar mientras trabaja el lector.
        target = moment + timedelta(minutes=5)
    minutes = choose_wait(target, moment, retry)
    validate_wait(call, minutes)
    return dict(plan, armed=True, status='prepared', environment=PREFIX + str(minutes),
                minutes=minutes, armed_utc=moment.isoformat(), mode=mode, step=step, retry=retry,
                earliest_wake_utc=(moment + timedelta(minutes=minutes)).isoformat(), sources_read=[])


def wake(root, moment, mode, step, enabled, armed, minutes, run_id, call=api):
    if minutes not in MINUTES or not str(run_id).isdigit():
        raise ValueError('La evidencia de la espera no es válida.')
    elapsed = (moment - instant(armed)).total_seconds()
    if elapsed < minutes * 60:
        raise ValueError('No se cumplió la espera prevista. No se ejecutarán fuentes.')
    validate_wait(call, minutes)
    proof = dict(mode=mode, step=step, observed_utc=moment.isoformat(), armed_utc=armed,
                 elapsed_seconds=elapsed, minimum_seconds=minutes * 60, run_id=str(run_id), sources_read=[])
    if mode == 'prueba':
        return dict(proof, status='proof_complete', final=step == 3)
    if not enabled or not workflow_active(call, CLOCK) or not workflow_active(call, REARM):
        return dict(proof, status='disabled')
    plan = snapshot(root, moment)  # Checkout nuevo de main después de la espera.
    if plan is None:
        return dict(proof, status='idle')
    if instant(plan['next_due_utc']) > moment:
        return dict(proof, status='waiting_for_deadline', **plan)
    if busy(call):
        return dict(proof, status='coordinator_busy', **plan)
    dispatch(call, COORDINATOR, dict(action='recovery', config_json='', expected='', request_id='reloj-' + str(run_id)))
    return dict(proof, status='coordinator_requested', **plan)


def next_cycle(mode, step, retry, conclusion):
    if mode == 'prueba':
        return dict(mode=mode, step=str(step + 1), retry='0') if conclusion == 'success' and step < 3 else None
    if conclusion == 'success':
        return dict(mode=mode, step='0', retry='0')
    if conclusion in ('failure', 'timed_out', 'startup_failure') and retry < 3:
        return dict(mode=mode, step='0', retry=str(retry + 1))
    return None  # Cancelación por reemplazo o límite de fallos: no crear un bucle.


def follow_up(event):
    """Solo producción confiable. El reloj no depende de su workflow_run."""
    row = event.get('workflow_run', {})
    if (event.get('action') != 'completed' or row.get('head_branch') != 'main'
            or row.get('head_repository', {}).get('full_name') != REPO
            or row.get('event') not in ('schedule', 'workflow_dispatch')):
        return None
    name = row.get('path', '').split('@', 1)[0].rsplit('/', 1)[-1]
    return dict(mode='real', step='0', retry='0') if name in PRODUCTION else None


def request_next(root, inputs, moment, enabled, call, cancel_idle=False):
    if inputs is None:
        return dict(status='no_rearm', sources_read=[])
    if inputs['mode'] == 'real':
        if not enabled:
            return dict(status='disabled', sources_read=[])
        if snapshot(root, moment) is None:
            if cancel_idle:
                cancel_waiters(call)
            return dict(status='idle', sources_read=[])
    if not workflow_active(call, CLOCK) or not workflow_active(call, REARM):
        return dict(status='disabled', sources_read=[])
    dispatch(call, CLOCK, inputs)
    return dict(status='next_wait_requested', **inputs, sources_read=[])


def renew(root, moment, mode, step, retry, enabled, preparation, awakening, call=api):
    outcomes = (preparation, awakening)
    if any(value not in ('success', 'failure', 'cancelled', 'skipped') for value in outcomes):
        raise ValueError('Resultados del ciclo no válidos.')
    if 'cancelled' in outcomes or preparation == 'skipped' or outcomes == ('success', 'skipped'):
        return dict(status='no_rearm', sources_read=[])
    conclusion = 'failure' if 'failure' in outcomes else 'success'
    return request_next(root, next_cycle(mode, step, retry, conclusion), moment, enabled, call)


def rearm(root, event, moment, enabled, call=api):
    # Algunos payloads webhook omiten path; verificarlo en el recurso oficial.
    row = event.get('workflow_run', {})
    if not row.get('path') and str(row.get('id', '')).isdigit():
        verified = call('GET', 'actions/runs/' + str(row['id']))
        if verified.get('status') != 'completed':
            return dict(status='event_not_completed', sources_read=[])
        event = dict(event, workflow_run=verified)
    return request_next(root, follow_up(event), moment, enabled, call, cancel_idle=True)


def emit(result):
    result['checked_utc'] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write('\n## Reloj automático FTR\n\nPreparar o renovar una espera no confirma una lectura de fuentes.\n\n```json\n' + text + '\n```\n')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            for key in ('armed', 'environment', 'minutes', 'armed_utc', 'status'):
                if key in result:
                    value = str(result[key]).lower() if isinstance(result[key], bool) else str(result[key])
                    stream.write(key + '=' + value + '\n')


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('El reloj solo se permite en main del repositorio FTR.')
    root = Path(__file__).resolve().parents[1]
    phase = os.environ.get('FTR_CLOCK_PHASE')
    enabled = os.environ.get('FTR_NATIVE_ENABLED') == 'true'
    moment = datetime.now(timezone.utc)
    if phase == 'rearm' and os.environ.get('GITHUB_EVENT_NAME') == 'workflow_run':
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
        result = rearm(root, event, moment, enabled)
    else:
        mode = os.environ.get('FTR_CLOCK_MODE')
        step, retry = os.environ.get('FTR_CLOCK_STEP', '0'), os.environ.get('FTR_CLOCK_RETRY', '0')
        if (os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch' or mode not in ('prueba', 'real')
                or step not in ('0', '1', '2', '3') or retry not in ('0', '1', '2', '3')
                or (mode == 'real' and step != '0') or (mode == 'prueba' and retry != '0')):
            raise ValueError('Los parámetros del reloj no son válidos.')
        if phase == 'prepare':
            result = prepare(root, moment, mode, int(step), int(retry), enabled)
        elif phase == 'renew':
            result = renew(root, moment, mode, int(step), int(retry), enabled,
                           os.environ['FTR_PREPARE_RESULT'], os.environ['FTR_WAKE_RESULT'])
        elif phase == 'wake':
            result = wake(root, moment, mode, int(step), enabled, os.environ['FTR_CLOCK_ARMED'],
                          int(os.environ['FTR_CLOCK_MINUTES']), os.environ['GITHUB_RUN_ID'])
        else:
            raise ValueError('Fase de reloj no permitida.')
    emit(result)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        emit(dict(status='error', message=str(exc) if isinstance(exc, ValueError) else
                  'No se pudo completar el reloj (' + type(exc).__name__ + '). No se confirma una actualización.', sources_read=[]))
        sys.exit(1)
