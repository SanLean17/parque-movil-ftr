"""Coordinador FTR: validación temporal, fuentes independientes, publicación comprobada.
La credencial Google solo se usa para leer la planilla. scraper.py y
actualizar_parques.py conservan sus algoritmos y se ejecutan con la configuración
activa en un directorio temporal. Nunca se usa force-push ni git add .
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _ftr_runtime.config import load, clean_config, digest, enabled, selected, current_slot, encoded, FILE
from _ftr_runtime.web import update_public
STATE = '_ftr_estado.json'
REPORT_DIR = Path(os.environ.get('FTR_REPORTE_DIR', str(Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir()))/'ftr-informe'))).resolve()


def now(): return datetime.now(timezone.utc)
def utc(): return now().isoformat()
def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def operation_event(operation, status, **details):
    """Recibo sin datos administrativos ni credenciales; compatible con 06.3."""
    event = dict(status=status, at=utc(), **details)
    operation.setdefault('events', []).append(event)
    operation.update(status=status, at=event['at'])
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR/'operacion.json').write_text(json.dumps(operation, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FTR: '+json.dumps(event, ensure_ascii=False))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write('\n- `'+status+'` — '+event['at']+'; '+json.dumps(details, ensure_ascii=False)+'\n')


def plan():
    old = load(ROOT)
    mode = os.environ.get('FTR_ACTION', 'scheduled')
    proposed = os.environ.get('FTR_CONFIG', '')
    config = clean_config(json.loads(proposed)) if proposed and mode in ('config', 'diagnostic') else old
    expected = os.environ.get('FTR_EXPECTED', '')
    if (mode == 'config' or expected) and expected != digest(old):
        raise ValueError('La configuración cambió desde otra computadora. Recargá y revisá el borrador antes de publicar.')
    state = read_json(ROOT/STATE, {})
    jobs = selected(config, old, state, mode, now())
    return mode, config, state, jobs


def public_output(key, value):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as f:
            f.write(key+'='+str(value).lower()+'\n')


def google_snapshot(root, config):
    sys.path.insert(0, str(ROOT/'_ftr_admin'))
    import diagnostico_administrativo as admin
    import estadisticas_periodo as statistics
    base = admin.base
    start = utc()
    source_id = base.spreadsheet_id(config['sheetUrl'])
    try:
        sheets = base.decode_xlsx(base.export_sheet(source_id))
    except base.DiagnosisError as exc:
        # DiagnosisError contiene mensajes controlados, sin contenido de celdas.
        raise ValueError(str(exc)) from None
    report, records = base.analyze(sheets, enabled(config), config['period'])
    base.add_comparison(report, records, root)
    detail = admin.extend_report(report, sheets, root, enabled(config), source_id, start)
    statistics.completar_estadisticas(report, admin.source_rows(sheets), now().astimezone(statistics.ZoneInfo('America/Argentina/Buenos_Aires')).date())
    report.update(inicio_lectura_utc=start, fin_prueba_utc=utc(), revision_repositorio=os.environ.get('GITHUB_SHA', 'local'))
    report['fecha_parque_comparado_utc'] = (root/'ultima_actualizacion_parque.txt').read_text().strip() if (root/'ultima_actualizacion_parque.txt').exists() else None
    detail.update(detectado_utc=start, revision_repositorio=report['revision_repositorio'])
    if ROOT == REPORT_DIR or ROOT in REPORT_DIR.parents:
        raise ValueError('El informe privado no puede guardarse dentro del repositorio.')
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR/'resumen.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (REPORT_DIR/'resumen.md').write_text(base.markdown(report)+'\n'+statistics.resumen_estadistico(report), encoding='utf-8')
    encrypted = admin.seal(detail, (ROOT/'_ftr_admin/diagnostico_publica.pem').read_bytes())
    (REPORT_DIR/'detalle_admin.enc.json').write_text(json.dumps(encrypted), encoding='utf-8')
    if not report['listo_para_revision_de_integracion']:
        raise ValueError('La lectura tiene errores de carga o tablas sin identificar. Revisá Incidencias; se conservaron los controles publicados.')
    for number in enabled(config):
        buf = io.StringIO(newline='')
        writer = csv.writer(buf, lineterminator='\n')
        writer.writerow(['linea','fecha','dominio','interno'])
        for domain, (date, internal) in sorted(records.get(number, {}).items()):
            writer.writerow([number, date.strftime('%d/%m/%Y'), domain, internal])
        (root/'controlados').mkdir(exist_ok=True)
        (root/'controlados'/f'linea{number}.csv').write_text(buf.getvalue(), encoding='utf-8-sig')
    from _ftr_runtime.history import write_history
    write_history(root, config, admin.source_rows(sheets), start,
                  now().astimezone(statistics.ZoneInfo('America/Argentina/Buenos_Aires')).date())
    (root/'ultima_actualizacion_controlados.txt').write_text(start+'\n', encoding='utf-8')
    return dict(read_utc=start, completed_utc=utc(), period=config['period'], source_id=source_id,
                records=report['totales_estadisticas']['registros_validos'], unique=report['totales_estadisticas']['unidades_unicas_por_linea'])


def cnrt_snapshot(root, config):
    """No reutiliza descargas antiguas si una consulta falla o devuelve vacío."""
    start = utc()
    with tempfile.TemporaryDirectory(prefix='ftr-cnrt-') as tmp:
        work = Path(tmp)
        for file in ('scraper.py','actualizar_parques.py'):
            shutil.copy2(ROOT/file, work/file)
        mapping = enabled(config)
        (work/'configuracion_lineas.py').write_text('LINEAS_EMPRESAS = '+repr(mapping)+'\nEMPRESAS_CNRT = sorted(set(LINEAS_EMPRESAS.values()))\n', encoding='utf-8')
        (work/'parques').mkdir()
        for script in ('scraper.py','actualizar_parques.py'):
            result = subprocess.run([sys.executable, str(work/script)], cwd=work, capture_output=True, timeout=2700)
            if result.returncode:
                raise ValueError('La consulta CNRT no terminó correctamente. Se conserva el parque anterior; no se publican descargas parciales.')
        sys.path.insert(0, str(ROOT/'_ftr_admin'))
        import diagnostico_administrativo as admin
        from _ftr_pruebas.planilla_anual import norm, line_number
        for number, company in mapping.items():
            file = work/'parques'/f'linea{number}.csv'
            if not file.exists() or not admin.fleet_rows(work, number):
                raise ValueError(f'CNRT no devolvió un parque validable para la Línea {number}. Se conserva el parque anterior.')
            with file.open(encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f)
                names={norm(x):x for x in reader.fieldnames or []}
                if not {'dominio','linea','empresanro'} <= names.keys():
                    raise ValueError('CNRT cambió columnas necesarias; descarga retenida.')
                seen=set()
                for row in reader:
                    if None in row or any(v is None for v in row.values()):
                        raise ValueError('CNRT produjo una fila desalineada; descarga retenida.')
                    ids={line_number(s.strip()) for s in re.split(r'[,;/|]',row[names['linea']])}
                    if number not in ids or line_number(row[names['empresanro']])!=company:
                        raise ValueError('Un vehículo no coincide con la línea y empresa configuradas; descarga retenida.')
                    domain=admin.base.plate(row[names['dominio']])
                    if not domain or domain in seen:
                        raise ValueError('El parque contiene dominios inválidos o duplicados; descarga retenida.')
                    seen.add(domain)
        for number in mapping:
            shutil.copy2(work/'parques'/f'linea{number}.csv', root/'parques'/f'linea{number}.csv')
    (root/'ultima_actualizacion_parque.txt').write_text(start+'\n', encoding='utf-8')
    return dict(read_utc=start, completed_utc=utc(), companies=len(set(mapping.values())), lines=len(mapping))


def gh(method, suffix, payload=None):
    import requests
    r=requests.request(method, 'https://api.github.com/repos/SanLean17/parque-movil-ftr/'+suffix,
        headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},
        json=payload,timeout=30,allow_redirects=False)
    if not r.ok:
        raise ValueError('GitHub no completó la publicación solicitada (HTTP '+str(r.status_code)+').')
    return r.json() if r.content else {}


def commit(root, paths):
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=root,text=True,stderr=subprocess.PIPE).strip()
    git('config','user.name','github-actions[bot]')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','--',*paths)
    if not git('diff','--cached','--name-only'):
        return git('rev-parse','HEAD')
    git('commit','-m','FTR: datos y configuración validados')
    git('push','origin','HEAD:main')
    return git('rev-parse','HEAD')


def build_pages(revision):
    gh('POST','pages/builds')
    for _ in range(40):
        time.sleep(10)
        built=gh('GET','pages/builds/latest')
        if built.get('commit')==revision:
            if built.get('status')=='built':
                verify_publication(revision)
                return
            if built.get('status')=='errored': break
    raise ValueError('Los datos se guardaron en GitHub, pero no se confirmó el despliegue de Pages. Revisá la ejecución antes de darlo por publicado.')


def public_hashes(root, config):
    files = ['index.html', 'linea.html', 'ftr-publica.js', 'ftr-datos.js', 'ftr-historial.js', 'ftr-historial-publico.js',
             'ultima_actualizacion_parque.txt', 'ultima_actualizacion_controlados.txt']
    files += [f'{folder}/linea{line}.csv' for folder in ('parques', 'controlados') for line in sorted(enabled(config))]
    files += [f'historial/linea{line}.json' for line in sorted(enabled(config))]
    return {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files if (root/name).is_file()}


def verify_publication(revision):
    """Pages construido no basta: verificar los archivos servidos por la web."""
    import requests
    from concurrent.futures import ThreadPoolExecutor
    expected = read_json(ROOT/'ftr_publicacion.json', {})
    if not expected.get('files_sha256'):
        raise ValueError('No hay un manifiesto verificable para confirmar la publicación.')
    base_url = 'https://sanlean.com.ar/parque-movil-ftr/'

    def fetch(path):
        response = requests.get(base_url+path, params={'ftr_revision': revision},
                                headers={'Cache-Control': 'no-cache'}, timeout=(10, 45))
        response.raise_for_status()
        return response

    for attempt in range(3):
        try:
            if fetch('ftr_publicacion.json').json() != expected:
                raise ValueError('Manifiesto anterior en la web.')
            def check(item):
                path, digest_value = item
                return hashlib.sha256(fetch(path).content).hexdigest() == digest_value
            with ThreadPoolExecutor(max_workers=6) as pool:
                if all(pool.map(check, expected.get('files_sha256', {}).items())):
                    return
        except (requests.RequestException, ValueError):
            pass
        if attempt < 2:
            time.sleep(10)
    raise ValueError('Los datos están guardados en GitHub y Pages terminó, pero la web aún no entrega todos los archivos de esta versión. Publicación pendiente de comprobar.')


def main():
    operation = dict(version=1, event=os.environ.get('GITHUB_EVENT_NAME', ''),
                     run_id=os.environ.get('GITHUB_RUN_ID'), events=[])
    request_id = os.environ.get('FTR_REQUEST_ID', '')
    cron = os.environ.get('FTR_CRON', '')
    if re.fullmatch(r'[A-Za-z0-9_-]{1,100}', request_id):
        operation['request_id'] = request_id
    if re.fullmatch(r'[0-9* /,\-]{1,80}', cron):
        operation['cron_utc'] = cron
    try:
        mode, config, state, jobs=plan()
        operation.update(action=mode, config_digest=digest(config))
        if os.environ.get('FTR_PHASE')=='check':
            public_output('work', bool(jobs) or mode=='config')
            public_output('cnrt', 'cnrt' in jobs)
            public_output('sources', ','.join(jobs))
            operation_event(operation, 'agenda_checked', sources=jobs, read=False)
            return 0
        prepared = os.environ.get('FTR_PLANNED_SOURCES')
        if prepared is not None:
            allowed = set(filter(None, prepared.split(',')))
            if not allowed <= {'cnrt', 'drive'}:
                raise ValueError('El plan de fuentes de esta ejecución no es válido.')
            # No agregar CNRT si su hora llegó durante la instalación y no se
            # preparó Chromium. El turno queda para la siguiente comprobación.
            jobs = [key for key in jobs if key in allowed]
        dry=os.environ.get('FTR_DRY_RUN')=='true' or mode=='diagnostic'
        if not dry and (os.environ.get('GITHUB_REF')!='refs/heads/main' or os.environ.get('GITHUB_REPOSITORY')!='SanLean17/parque-movil-ftr'):
            raise ValueError('La publicación real solo se permite desde main de este repositorio.')
        if not jobs and mode!='config': return 0
        with tempfile.TemporaryDirectory(prefix='ftr-validacion-') as tmp:
            stage=Path(tmp)
            for name in ('parques','controlados'):
                shutil.copytree(ROOT/name,stage/name)
            if (ROOT/'historial').exists():
                shutil.copytree(ROOT/'historial',stage/'historial')
            for name in ('ultima_actualizacion_parque.txt','ultima_actualizacion_controlados.txt','index.html','linea.html'):
                if (ROOT/name).exists():shutil.copy2(ROOT/name,stage/name)
            paths=[]; errors=[]; results={}
            for key in jobs:
                from _ftr_runtime.agenda import eligible_slot, slot_satisfied
                slot = eligible_slot(config, state, key, now())
                kind = ('additional' if mode == 'scheduled' and operation['event'] == 'schedule'
                        and (not slot or slot_satisfied(state, key, slot)) else
                        'scheduled' if mode == 'scheduled' else 'configuration' if mode == 'config' else 'manual')
                state.setdefault(key,{})['attempt_utc']=utc()
                operation_event(operation, 'reading_started', source=key,
                                configured_time=config[key]['time'], interval_days=config[key]['days'],
                                requested_slot=slot, reading_kind=kind)
                try:
                    data=cnrt_snapshot(stage,config) if key=='cnrt' else google_snapshot(stage,config)
                    read_at = datetime.fromisoformat(data['read_utc'])
                    state[key].update(data,status='success',run_id=os.environ.get('GITHUB_RUN_ID'),served_slot=current_slot(config,key,read_at),error=None)
                    results[key]=data
                    operation_event(operation, 'reading_finished', source=key,
                                    read_utc=data['read_utc'], completed_utc=data['completed_utc'])
                except Exception as exc:
                    message=str(exc) if isinstance(exc,ValueError) else 'La fuente no pudo procesarse ('+type(exc).__name__+'); se conserva su último resultado válido.'
                    errors.append(message);state[key].update(status='error',error=message)
                    operation_event(operation, 'source_error', source=key, message=message)
            if mode=='config' and errors:
                raise ValueError('No se aplicó la configuración. '+' '.join(errors))
            if dry:
                print('Validación terminada. Sin cambiar datos, configuración o web.')
                return 1 if errors else 0
            for key in results:
                folder, stamp=('parques','ultima_actualizacion_parque.txt') if key=='cnrt' else ('controlados','ultima_actualizacion_controlados.txt')
                for number in enabled(config):
                    dest=ROOT/folder/f'linea{number}.csv'
                    shutil.copy2(stage/folder/dest.name,dest);paths.append(str(dest.relative_to(ROOT)))
                shutil.copy2(stage/stamp,ROOT/stamp);paths.append(stamp)
                if key=='drive':
                    for number in enabled(config):
                        history=stage/'historial'/f'linea{number}.json'
                        if history.is_file():
                            (ROOT/'historial').mkdir(exist_ok=True)
                            shutil.copy2(history,ROOT/'historial'/history.name)
                            paths.append('historial/'+history.name)
            if mode=='config':
                (ROOT/FILE).write_bytes(encoded(config));paths.append(FILE)
            update_public(ROOT,config)
            paths.extend(['index.html','linea.html'])
            state.update(version=2,config_digest=digest(config),updated_utc=utc(),run_id=os.environ.get('GITHUB_RUN_ID'))
            (ROOT/STATE).write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');paths.append(STATE)
            manifest=dict(version=state['updated_utc'],period=state.get('drive',{}).get('period',config['period']),config_digest=digest(config),run_id=os.environ.get('GITHUB_RUN_ID'),lines=sorted(enabled(config)),files_sha256=public_hashes(ROOT,config))
            (ROOT/'ftr_publicacion.json').write_text(json.dumps(manifest)+'\n',encoding='utf-8');paths.append('ftr_publicacion.json')
            revision=commit(ROOT,paths)
            operation_event(operation, 'configuration_saved' if mode=='config' else 'data_saved' if results else 'state_saved', revision=revision, sources=list(results))
            operation_event(operation, 'publication_pending', revision=revision)
            build_pages(revision)
            operation_event(operation, 'data_published' if results else 'configuration_published' if mode=='config' else 'state_published', revision=revision, sources=list(results))
            if errors:
                operation_event(operation, 'source_errors', message=' '.join(errors))
                print('Hubo una fuente con errores; su último resultado válido se conservó.')
                return 1
        return 0
    except Exception as exc:
        message=str(exc) if isinstance(exc,ValueError) else 'La operación no pudo completarse ('+type(exc).__name__+'). Revisá el estado; no se fuerza ninguna publicación.'
        print(message)
        operation['message'] = message
        operation_event(operation, 'error', message=message)
        return 1

if __name__=='__main__':sys.exit(main())
