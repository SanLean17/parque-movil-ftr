"""Complete, bounded-in-time GitHub evidence for local orders. GET requests only."""
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

WORKFLOWS={'ftr_sincronizar.yml','actualizar_parques.yml','ftr_extraordinarias.yml','ftr_recuperar_turnos.yml','ftr_estadisticas_admin.yml'}
TITLE=re.compile(r'^FTR · ([a-z-]+) · ([a-f0-9]{32})$')

def utc(value):
    value=datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
    if value.tzinfo is None:raise ValueError('La fecha de la orden no incluye zona horaria.')
    return value.astimezone(timezone.utc)

class RunScan(list):
    def __init__(self,rows,evidence):
        super().__init__(rows);self.evidence=evidence

def scan(api,since,classify,now=None):
    end=utc(now or datetime.now(timezone.utc)).replace(microsecond=0)
    start=(utc(since)-timedelta(minutes=5)).replace(microsecond=0)
    if start>end:raise ValueError('Revisá la fecha y hora de Windows antes de comprobar el envío.')
    calls=0;started=time.monotonic();found={}
    def get(path):
        nonlocal calls
        if time.monotonic()-started>120:raise ValueError('La consulta no terminó: no se habilita resolver una búsqueda incompleta.')
        calls+=1;return api('GET',path)
    def stamp(d):return d.strftime('%Y-%m-%dT%H:%M:%SZ')
    def window(lo,hi):
        def page(n):
            query=urlencode(dict(branch='main',created=stamp(lo)+'..'+stamp(hi),per_page=100,page=n))
            return get('actions/runs?'+query)
        data=page(1);total=data.get('total_count');rows=data.get('workflow_runs')
        if type(total) is not int or not isinstance(rows,list):raise ValueError('GitHub no confirmó la cobertura de la búsqueda.')
        # GitHub caps filtered searches at 1000. Split before reaching the cap.
        if total>=1000:
            seconds=int((hi-lo).total_seconds())
            if seconds<1:raise ValueError('Demasiadas ejecuciones en el mismo segundo: la búsqueda no puede confirmarse completa.')
            middle=lo+timedelta(seconds=seconds//2)
            window(lo,middle);window(middle+timedelta(seconds=1),hi);return
        collected={}
        for number in range(1,max(1,(total+99)//100)+1):
            if number>1:
                data=page(number);rows=data.get('workflow_runs')
                if data.get('total_count')!=total:raise ValueError('La lista de GitHub cambió durante la consulta. Comprobá nuevamente.')
            if not isinstance(rows,list):raise ValueError('GitHub devolvió una página incompleta.')
            for row in rows:
                if row['id'] in collected or not lo<=utc(row['created_at'])<=hi:raise ValueError('No se pudo verificar la paginación de GitHub.')
                collected[row['id']]=row
        if len(collected)!=total:raise ValueError('Faltan ejecuciones en la respuesta de GitHub. No se habilita resolver la orden.')
        found.update(collected)
    window(start,end)
    # An older run can still own the publication queue. Include current active
    # executions even when they were created before the order's search window.
    for status in ('queued','in_progress','waiting','pending','requested'):
        number=1;seen=set()
        while True:
            data=get('actions/runs?'+urlencode(dict(branch='main',status=status,per_page=100,page=number)))
            total=data.get('total_count');batch=data.get('workflow_runs')
            if type(total) is not int or not isinstance(batch,list) or total>=1000:
                raise ValueError('No se pudieron comprobar todas las ejecuciones activas de GitHub.')
            for row in batch:
                if row['id'] in seen:raise ValueError('La lista de ejecuciones activas cambió. Comprobá nuevamente.')
                seen.add(row['id']);found[row['id']]=row
            if len(seen)==total:break
            if not batch or len(seen)>total:raise ValueError('La consulta de ejecuciones activas quedó incompleta.')
            number+=1
    result=[]
    for row in found.values():
        workflow=row.get('path','').split('@')[0].rsplit('/',1)[-1]
        if workflow not in WORKFLOWS:continue
        match=TITLE.fullmatch(row.get('display_title',''))
        item=dict(id=row['id'],status=row['status'],conclusion=row.get('conclusion'),
                  request_id=match[2] if match else None,action=match[1] if match else None,
                  url=row.get('html_url'),created_at=row['created_at'],workflow=workflow,
                  run_attempt=row.get('run_attempt',1))
        if match and row['status']=='completed':
            jobs=[];number=1
            while True:
                data=get(f"actions/runs/{row['id']}/attempts/{item['run_attempt']}/jobs?per_page=100&page={number}")
                batch=data.get('jobs');total=data.get('total_count')
                if not isinstance(batch,list) or type(total) is not int:raise ValueError('No se pudo comprobar el resultado de la ejecución.')
                jobs.extend(batch)
                if len(jobs)>=total:break
                if not batch:raise ValueError('Faltan trabajos de la ejecución.')
                number+=1
            item.update(classify(row,jobs))
            steps=[s for j in jobs for s in j.get('steps',[])]
            if workflow=='ftr_estadisticas_admin.yml' and row.get('conclusion')=='success':
                verified=any(s.get('name')=='Guardar diccionario o importar histórico aislado' and s.get('conclusion')=='success' for s in steps)
                if verified:
                    action=item['action']
                    item.update(effect='dictionary' if action=='dictionary-save' else 'historical_review' if action=='history-review' else 'historical',
                        detail='Regla guardada; aplicación pendiente de una lectura o revisión.' if action=='dictionary-save' else 'Informe protegido preparado; no se publicó ningún cambio.' if action=='history-review' else 'Estadísticas publicadas y verificadas.')
        result.append(item)
    return RunScan(result,dict(complete=True,from_utc=stamp(start),through_utc=stamp(end),
        checked_at=datetime.now(timezone.utc).isoformat(),requests=calls,examined=len(found)))
