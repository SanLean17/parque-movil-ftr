"""Panel 06.3: diferencia comprobación, guardado y actualización de datos.
No ejecuta procesos al arrancar o al consultar su estado.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server
from _ftr_runtime.agenda import describe

_cache = {}


def classify_run(run, jobs):
    status = run['status']
    if status != 'completed':
        return {'effect': 'running', 'label': 'En ejecución' if status == 'in_progress' else 'En espera', 'detail': 'Todavía no confirma una actualización.'}
    if run.get('conclusion') != 'success':
        return {'effect': 'failed', 'label': 'Revisar ejecución', 'detail': 'Finalizó con error o fue cancelada; no confirma datos nuevos.'}
    steps = [s for job in jobs for s in job.get('steps', [])]
    process = next((s for s in steps if s.get('name') == 'Procesar, validar, guardar y publicar'), None)
    checked = any(s.get('name') == 'Comprobar agenda o solicitud' and s.get('conclusion') == 'success' for s in steps)
    if checked and process and process.get('conclusion') == 'skipped':
        return {'effect': 'agenda_only', 'label': 'Agenda comprobada', 'detail': 'Sin lectura de fuentes; no correspondía actualizar.'}
    if process and process.get('conclusion') == 'success':
        title = run.get('display_title', '')
        if any(s.get('name')=='Publicación recuperada sin nueva lectura' and s.get('conclusion')=='success' for s in steps):
            return {'effect':'publication','label':'Publicación recuperada','detail':'Se publicaron y verificaron los datos guardados, sin leer las fuentes otra vez.'}
        if any(s.get('name')=='Solicitud cubierta por una ejecución coincidente' and s.get('conclusion')=='success' for s in steps):
            return {'effect':'coalesced','label':'Coincidió con otra actualización','detail':'Se comparte su resultado confirmado; no se volvió a leer la fuente.'}
        if '· oneoff-set ·' in title or '· oneoff-cancel ·' in title:
            return {'effect':'oneoff_saved','label':'Programación extraordinaria guardada','detail':'Cambio publicado en GitHub, sin leer fuentes ni modificar el calendario recurrente.'}
        if '· config ·' in title:
            return {'effect': 'configuration', 'label': 'Configuración guardada', 'detail': 'La fecha de última lectura indica si también se consultaron las fuentes.'}
        if '· diagnostic ·' in title:
            return {'effect': 'diagnostic', 'label': 'Diagnóstico realizado', 'detail': 'Prueba de lectura sin publicar datos.'}
        origin='Recuperación automática' if '· recovery ·' in title else 'PROGRAMADA MANUALMENTE' if '· oneoff ·' in title else 'Automática recurrente' if run.get('event')=='schedule' else 'Actualizar todo' if '· all ·' in title else 'Actualizar ahora'
        return {'effect': 'updated', 'label': 'Actualización completada', 'detail': origin+'. Procesamiento y publicación finalizados correctamente.'}
    return {'effect': 'unknown', 'label': 'Ejecución finalizada', 'detail': 'No se pudo comprobar si hubo una lectura nueva.'}


def last_runs():
    rows_by_id = {}
    # Un calendario y una entrada manual comparten el mismo coordinador.
    # El panel debe ver también las ejecuciones del calendario original.
    for workflow in (server.WORKFLOW, 'actualizar_parques.yml','ftr_extraordinarias.yml','ftr_recuperar_turnos.yml'):
        for row in server.api('GET', 'actions/workflows/'+workflow+'/runs?branch=main&per_page=6').get('workflow_runs', []):
            rows_by_id[row['id']] = row
    rows = sorted(rows_by_id.values(), key=lambda r: (r['created_at'], r['id']), reverse=True)[:6]
    result = []
    for r in rows:
        key = (r['id'], r.get('run_attempt', 1), r.get('updated_at'), r['status'], r.get('conclusion'))
        if r['status'] != 'completed':
            effect = classify_run(r, [])
        elif key in _cache:
            effect = _cache[key]
        else:
            try:
                jobs = server.api('GET', f"actions/runs/{r['id']}/jobs?per_page=100").get('jobs', [])
                effect = classify_run(r, jobs)
                if len(_cache) >= 100:
                    _cache.clear()
                _cache[key] = effect
            except (ValueError, server.requests.RequestException):
                effect = {'effect': 'unknown', 'label': 'Detalle no disponible', 'detail': 'No se confirma una actualización; se conserva la fecha de última lectura.'}
        result.append(dict(id=r['id'], title=r.get('display_title', r.get('name', 'Ejecución')), status=r['status'],
                           conclusion=r.get('conclusion'), url=r['html_url'], created_at=r['created_at'],
                           event=r.get('event'), started_at=r.get('run_started_at'), updated_at=r.get('updated_at'),run_attempt=r.get('run_attempt', 1), **effect))
    return result


def status():
    result = server.remote()
    result['state'] = server.json_file('_ftr_estado.json')
    result['runs'] = last_runs()
    result['schedule'] = describe(result['config'], result['state'], datetime.now(timezone.utc))
    return server.jsonify(result)


def install():
    server.VERSION = '06.3'
    server.last_runs = last_runs
    server.app.view_functions['status'] = status


if __name__ == '__main__':
    install()
    server.main()
