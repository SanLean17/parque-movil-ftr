"""Una cita por fuente, persistida en GitHub; ninguna espera ni reloj local.

El reclamo se publica antes de leer. Un intento interrumpido no vuelve a leer
por una entrega duplicada. Solo el workflow común posee la exclusión mutua.
"""
import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .config import ZONE, current_slot
from . import native_schedule

FILE='_ftr_extraordinarias.json'
WORKFLOW='.github/workflows/ftr_extraordinarias.yml'
ACTIONS=('oneoff-set','oneoff-cancel','oneoff')
PAST='La fecha y hora deben ser posteriores al momento actual.'
EXPIRED='La fecha programada ya pasó. Elegí una nueva fecha y horario.'


def instant(value):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None:raise ValueError()
        return result
    except (ValueError,TypeError,AttributeError):raise ValueError('La fecha programada no es válida.') from None


def empty():return dict(version=1,pending={},history=[],last_execution={},receipts={})


def load(root):
    path=Path(root)/FILE
    if not path.exists():return empty()
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('version')!=1 or not isinstance(data.get('history'),list) or any(not isinstance(data.get(k),dict) for k in ('pending','last_execution','receipts')):
        raise ValueError('No se pudo verificar la programación extraordinaria. No se ejecutarán fuentes.')
    for key,row in data['pending'].items():
        if key not in ('drive','cnrt') or row.get('source')!=key or not re.fullmatch('[a-f0-9]{32}',row.get('id','')):
            raise ValueError('La programación extraordinaria no es válida.')
        instant(row.get('at'))
    return data


def command(value,moment,cancel=False,expired_message=False):
    if not isinstance(value,dict) or value.get('source') not in ('drive','cnrt'):
        raise ValueError('Elegí Drive o CNRT.')
    expected=value.get('expected_id')
    if expected is not None and not re.fullmatch('[a-f0-9]{32}',str(expected)):
        raise ValueError('La programación consultada no es válida. Actualizá el estado.')
    result=dict(source=value['source'],expected_id=expected)
    if cancel:return result
    try:
        day=value['date'];clock=value['time']
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',clock):raise ValueError()
        when=datetime.fromisoformat(day+'T'+clock).replace(tzinfo=ZoneInfo(ZONE))
    except (ValueError,TypeError,KeyError):raise ValueError('Completá una fecha y un horario válidos.') from None
    if when<=moment:raise ValueError(EXPIRED if expired_message else PAST)
    if when>moment+timedelta(days=366):raise ValueError('Elegí una fecha dentro de los próximos 366 días.')
    result.update(date=day,time=clock,at=when.isoformat())
    return result


def render(data):
    crons=[]
    for row in data['pending'].values():
        utc=instant(row['at']).astimezone(timezone.utc)
        cron=f'{utc.minute} {utc.hour} {utc.day} {utc.month} *'
        if cron not in crons:crons.append(cron)
    lines=['# FTR-ONEOFF-V1 — generado; fecha completa y consumo único en '+FILE,
           'name: FTR - Actualización extraordinaria',
           'run-name: FTR · oneoff · PROGRAMADA MANUALMENTE','on:']
    if crons:lines+=['  schedule:']+[f"    - cron: '{c}'" for c in sorted(crons)]
    lines+=['  workflow_dispatch:','permissions:','  contents: write','  pages: write','  actions: read','jobs:',
            '  actualizar:','    uses: ./.github/workflows/ftr_sincronizar.yml','    with:',
            '      action: oneoff','    secrets: inherit','']
    return '\n'.join(lines)


def save(root,data,commit):
    root=Path(root);workflow=root/WORKFLOW;content=render(data)
    changed=not workflow.exists() or workflow.read_text(encoding='utf-8-sig')!=content
    if changed:native_schedule.authorization()  # Antes de escribir o consultar fuentes.
    (root/FILE).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    paths=[FILE]
    if changed:
        workflow.parent.mkdir(parents=True,exist_ok=True);workflow.write_text(content,encoding='utf-8',newline='\n');paths.append(WORKFLOW)
    return commit(root,paths)


def apply_command(root,action,payload,identifier,moment,commit):
    if not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('La orden necesita un identificador válido.')
    data=load(root)
    if identifier in data['receipts']:return None
    change=command(payload,moment,action=='oneoff-cancel',True);key=change['source'];old=data['pending'].get(key)
    if (old or {}).get('id')!=change['expected_id']:
        raise ValueError('La actualización programada cambió. Actualizá el estado antes de reemplazarla o cancelarla.')
    if old:
        data['history'].append(dict(old,status='cancelled' if action=='oneoff-cancel' else 'replaced',finished_utc=moment.isoformat()))
        del data['pending'][key]
    if action=='oneoff-set':
        data['pending'][key]=dict(id=identifier,source=key,at=change['at'],created_utc=moment.isoformat(),status='pending')
    data['receipts'][identifier]=dict(status='success',action=action,at=moment.isoformat())
    return save(root,data,commit)


def recover_interrupted(data,moment):
    # El coordinador tiene timeout de 90 minutos. Se deja margen antes de
    # diagnosticar un reclamo cuyo resultado nunca llegó a publicarse.
    changed=False
    for row in [*data.get('history',[]),*data.get('execution_history',[]),*data.get('last_execution',{}).values(),*data.get('receipts',{}).values()]:
        if row.get('status')=='running' and row.get('started_utc') and moment-instant(row['started_utc'])>timedelta(minutes=95):
            # El límite permite detectar la interrupción, no conocer su hora real.
            # No inventar finished_utc ni una lectura para cerrar el historial.
            row.update(status='error',detected_utc=moment.isoformat(),timeout_utc=(instant(row['started_utc'])+timedelta(minutes=90)).isoformat(),error='La ejecución terminó o se interrumpió sin publicar un resultado confirmado. Revisá su ejecución en GitHub y reprogramá si hace falta.')
            changed=True
    return changed


def resolve(root,mode,config,state,jobs,moment,payload=None,identifier='',cron='',event_created=None,run_id=None):
    enabled=(Path(root)/FILE).exists() or mode in ACTIONS
    data=load(root) if enabled else empty();interrupted=recover_interrupted(data,moment);normal=list(jobs);due={};expired=[]
    if mode in ('scheduled','recovery','oneoff','drive','cnrt','all'):
        for key,row in data['pending'].items():
            if instant(row['at'])<=moment and (mode in ('scheduled','recovery','oneoff','all') or key==mode):
                if moment-instant(row['at'])>timedelta(days=1):expired.append(key)
                else:due[key]=row
    jobs=list(dict.fromkeys([*jobs,*due]));shared={}
    requested=(payload or {}).get('requested_utc') if mode in ('drive','cnrt','all') else None
    if mode in ('scheduled','recovery','oneoff'):requested=event_created
    receipt=data['receipts'].get(identifier) if identifier else None
    for key in list(jobs):
        last=data['last_execution'].get(key,{})
        from .agenda import eligible_slot,slot_satisfied
        slot=eligible_slot(config,state,key,moment)
        calendar_pending=mode in ('scheduled','recovery') and key in normal and slot and not slot_satisfied(state,key,slot)
        if run_id and mode in ('scheduled','recovery','oneoff') and str(last.get('run_id'))==str(run_id):
            shared[key]=last;jobs.remove(key)
        elif receipt and mode in ('drive','cnrt','all'):
            shared[key]=receipt;jobs.remove(key)
        elif requested and not calendar_pending and last.get('finished_utc') and instant(last['finished_utc'])>=max(instant(requested),instant(due[key]['at']) if key in due else instant(requested)):
            shared[key]=last;jobs.remove(key)
        elif requested and last.get('status')=='running' and last.get('started_utc') and instant(last['started_utc'])<=instant(requested):
            shared[key]=last;jobs.remove(key)
        elif mode=='scheduled' and cron and 'PROGRAMADA MANUALMENTE' in last.get('reasons',[]):
            # La política adicional de Drive sigue activa en otros arranques.
            # Solo se absorbe el aviso del MISMO horario ya consumido.
            fields=cron.split();slot=current_slot(config,key,moment)
            for row in reversed(data['history']):
                if row['source']!=key or row.get('run_id')!=last.get('run_id'):continue
                at=instant(row['at']);utc=at.astimezone(timezone.utc)
                same_cron=len(fields)==5 and all(f in ('*',str(v)) for f,v in zip(fields[:4],(utc.minute,utc.hour,utc.day,utc.month)))
                if slot and instant(slot.split(':',1)[1])==at and same_cron and moment-at<timedelta(days=1):
                    shared[key]=last;jobs.remove(key)
                break
    pure=[]
    for key in jobs:
        if key not in normal:
            slot=current_slot(config,key,instant(due[key]['at'])) if key in due else None
            exact=bool(config[key]['enabled'] and slot and instant(slot.split(':',1)[1])==instant(due[key]['at']))
            if not exact:pure.append(key)
            elif key not in normal:normal.append(key)
    from .agenda import eligible_slot,slot_satisfied,slot_time
    expected={}
    for key in jobs:
        slot=eligible_slot(config,state,key,moment)
        if key not in pure and slot and not slot_satisfied(state,key,slot):expected[key]=slot_time(slot).astimezone(timezone.utc).isoformat()
    return dict(enabled=enabled,data=data,jobs=jobs,normal=normal,due=due,expired=expired,shared=shared,pure=pure,identifier=identifier,expected=expected,mode=mode,cron=cron,event_created=event_created,interrupted=interrupted)


def claim(root,plan,moment,run_id,commit):
    if not plan['enabled']:return
    data=plan['data'];stamp=moment.isoformat()
    if any(r.get('status')!='success' for r in plan['shared'].values()):
        if plan['interrupted']:save(root,data,commit)
        raise ValueError('La ejecución coincidente terminó con error o no tiene resultado confirmado. No se vuelve a ejecutar automáticamente; revisá el historial.')
    for key in plan['expired']:
        row=data['pending'].pop(key);data['history'].append(dict(row,status='error',finished_utc=stamp,error='GitHub no inició esta cita dentro de las 24 horas siguientes. Reprogramala.'))
    for key,last in plan['shared'].items():
        if key in plan['due']:
            row=data['pending'].pop(key);data['history'].append(dict(row,status='success',started_utc=last.get('started_utc'),finished_utc=last.get('finished_utc'),run_id=last.get('run_id'),reasons=['PROGRAMADA MANUALMENTE','resultado compartido']))
    for key in plan['jobs']:
        reasons=['PROGRAMADA MANUALMENTE'] if key in plan['due'] else []
        if key in plan['normal']:reasons.append('actualización solicitada o recurrente')
        data['last_execution'][key]=dict(source=key,started_utc=stamp,status='running',run_id=run_id,reasons=reasons)
        expected=plan['expected'].get(key)
        delay=max(0,int((moment-instant(expected)).total_seconds())) if expected else None
        kind=('recovered' if expected and (plan['mode']=='recovery' or delay>=1800) else
              'delayed' if expected and delay>60 else 'scheduled' if expected else
              'oneoff' if key in plan['due'] else 'additional' if plan['mode']=='scheduled' else 'manual')
        trace=dict(data['last_execution'][key],expected_utc=expected,delay_seconds=delay,kind=kind,action=plan['mode'],cron_utc=plan['cron'],event_created_utc=plan['event_created'])
        data['last_execution'][key]=trace
        history=data.setdefault('execution_history',[]);history.append(dict(trace));data['execution_history']=history[-200:]
        if key in plan['due']:
            row=data['pending'].pop(key);data['history'].append(dict(row,status='running',started_utc=stamp,run_id=run_id,reasons=reasons))
    if plan['identifier'] and (plan['jobs'] or plan['shared']):
        data['receipts'][plan['identifier']]=dict(status='running' if plan['jobs'] else 'success',started_utc=stamp,run_id=run_id)
    if plan['jobs'] or plan['expired'] or plan['shared'] or plan['interrupted']:save(root,data,commit)


def finish(root,plan,key,moment,success,error=None,read_utc=None):
    if not plan['enabled']:return
    data=plan['data'];status='success' if success else 'error';stamp=moment.isoformat()
    last=data['last_execution'][key];last.update(status=status,finished_utc=stamp,error=error)
    if read_utc:
        last['read_utc']=read_utc
        expected=plan['expected'].get(key)
        if expected:
            delay=max(0,int((instant(read_utc)-instant(expected)).total_seconds()))
            last.update(expected_utc=expected,delay_seconds=delay,kind='recovered' if plan['mode']=='recovery' or delay>=1800 else 'delayed' if delay>60 else 'scheduled')
    for row in data.get('execution_history',[]):
        if row['source']==key and row.get('status')=='running' and row.get('run_id')==last['run_id']:row.update(last)
    # Una cita vencida mientras esta misma fuente estaba leyendo comparte el resultado.
    pending=data['pending'].get(key)
    if pending and instant(last['started_utc'])<=instant(pending['at'])<=moment:
        row=data['pending'].pop(key);data['history'].append(dict(row,status='running',started_utc=last['started_utc'],run_id=last['run_id'],reasons=['PROGRAMADA MANUALMENTE','coincidió con una ejecución en curso']))
    for row in data['history']:
        if row['source']==key and row.get('status')=='running' and row.get('run_id')==last['run_id']:
            row.update(status=status,finished_utc=stamp,error=error)
    identifier=plan['identifier']
    if identifier:
        receipt=data['receipts'][identifier]
        if not success:receipt['status']='error'
        elif receipt['status']!='error' and all(data['last_execution'][k]['status']!='running' for k in plan['jobs']):receipt['status']='success'
        receipt['finished_utc']=stamp


def stage_finish(root,plan,paths):
    if not plan['enabled']:return
    root=Path(root);content=render(plan['data']);workflow=root/WORKFLOW
    if not workflow.exists() or workflow.read_text(encoding='utf-8-sig')!=content:
        native_schedule.authorization();workflow.write_text(content,encoding='utf-8',newline='\n');paths.append(WORKFLOW)
    (root/FILE).write_text(json.dumps(plan['data'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');paths.append(FILE)


def preserve_calendar(state,key):
    row=state.setdefault(key,{})
    if 'recurrence' not in row:
        row['recurrence']={k:copy.deepcopy(row[k]) for k in ('status','read_utc','attempt_utc','served_slot') if k in row}
