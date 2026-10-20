"""Mantenimiento de workflows. Sin acceso a Google/CNRT ni modificación de datos."""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = 'SanLean17/parque-movil-ftr'
LIVE = 'ftr_sincronizar.yml'
SELF = 'ftr_mantenimiento_agenda.yml'
RETIRED = (
    'probar_planilla_anual.yml',
    'ftr_integracion_pruebas.yml',
    'ftr_correccion061.yml',
    'ftr_agenda_pruebas062.yml',
    'actualizar_parques.yml',
)
FILES = ('_ftr_config.json', '_ftr_estado.json',
         'ultima_actualizacion_controlados.txt', 'ultima_actualizacion_parque.txt')
BASE = f'https://api.github.com/repos/{REPO}/'


def api(method, suffix):
    if method == 'PUT':
        allowed = {f'actions/workflows/{name}/{action}'
                   for name in (*RETIRED, LIVE, SELF) for action in ('enable', 'disable')}
        if suffix not in allowed:
            raise RuntimeError('Escritura fuera del alcance de mantenimiento.')
    elif method != 'GET':
        raise RuntimeError('No se permite ejecutar, cancelar ni publicar fuentes.')
    request = urllib.request.Request(
        BASE + suffix, method=method,
        data=b'' if method == 'PUT' else None,
        headers={'Accept': 'application/vnd.github+json',
                 'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'X-GitHub-Api-Version': '2022-11-28',
                 'User-Agent': 'FTR-Mantenimiento-Autorizado'},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'GitHub HTTP {exc.code}: {method} {suffix}') from None


def workflow(name):
    value = api('GET', 'actions/workflows/' + name)
    if value.get('path') != '.github/workflows/' + name:
        raise RuntimeError('Ruta de workflow no coincidente; no se modifica.')
    return value


def snapshot():
    return {name: api('GET', 'contents/' + name + '?ref=main')['sha'] for name in FILES}


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO:
        raise RuntimeError('Repositorio distinto del autorizado.')
    if os.environ.get('GITHUB_REF') != 'refs/heads/ftr/mantenimiento-agenda':
        raise RuntimeError('La tarea solo se autoriza en la rama de mantenimiento.')
    report = {'started_utc': datetime.now(timezone.utc).isoformat(),
              'sources_requested': False, 'files_written': False,
              'retired': [], 'reset': None}
    try:
        report['files_before'] = snapshot()
        live = workflow(LIVE)
        report['live_before'] = live['state']
        workflows = api('GET', 'actions/workflows?per_page=100')['workflows']
        report['workflows_before'] = [{'path': w['path'], 'state': w['state']} for w in workflows]
        runs = api('GET', 'actions/workflows/' + LIVE + '/runs?per_page=50')['workflow_runs']
        report['recent_automatic'] = [
            {'id': r['id'], 'created_at': r['created_at'], 'status': r['status'],
             'conclusion': r.get('conclusion')}
            for r in runs if r['event'] == 'schedule'
        ][:5]
        active = [r['id'] for r in runs if r['status'] != 'completed']
        if active:
            raise RuntimeError('Hay una ejecución activa. No se reinicia ni se cancela: ' + str(active))
        known = {w['path'] for w in workflows}
        for name in RETIRED:
            if '.github/workflows/' + name not in known:
                report['retired'].append({'file': name, 'state': 'not_found'})
                continue
            previous = workflow(name)['state']
            api('PUT', 'actions/workflows/' + name + '/disable')
            current = workflow(name)['state']
            report['retired'].append({'file': name, 'before': previous, 'state': current})
            if current != 'disabled_manually':
                raise RuntimeError('No se confirmó la desactivación de ' + name)
        # Reinicio reversible del workflow, NO una ejecución de lectura.
        try:
            if live['state'] == 'active':
                api('PUT', 'actions/workflows/' + LIVE + '/disable')
                report['reset'] = 'disabled_for_reactivation'
        finally:
            enabled = False
            for attempt in range(4):
                try:
                    api('PUT', 'actions/workflows/' + LIVE + '/enable')
                    enabled = workflow(LIVE)['state'] == 'active'
                    if enabled:
                        break
                except RuntimeError:
                    if attempt == 3:
                        raise
                time.sleep(2 ** attempt)
            if not enabled:
                raise RuntimeError('Reactivar FTR - Sincronizar desde Actions: no se pudo confirmar active.')
        report['reset'] = 'reactivated_no_manual_run'
        report['live_after'] = workflow(LIVE)['state']
        report['files_after'] = snapshot()
        report['files_unchanged'] = report['files_before'] == report['files_after']
        print('FTR - Sincronizar: active. Workflows retirados: disabled_manually.')
        print('No se solicitó lectura de Google, descarga de CNRT ni actualización manual.')
        print('Queda por verificar una ejecución cuyo evento sea schedule.')
    except Exception as exc:
        report['error'] = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        raise
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        output = Path(os.environ['RUNNER_TEMP']) / 'ftr-auditoria-agenda.json'
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
            summary.write('# Mantenimiento de agenda (sin leer fuentes)\n\n```json\n')
            summary.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n```\n')


if __name__ == '__main__':
    main()
