"""Comprobación remota de programación; solo GET y sin consultar fuentes."""
import base64
import json
import os
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from . import native_schedule, oneoff

WORKFLOWS=('actualizar_parques.yml','ftr_recuperar_turnos.yml','ftr_extraordinarias.yml','ftr_sincronizar.yml')


def github_get(path):
    token=os.environ.get('GITHUB_TOKEN','')
    if not token:raise ValueError('No se puede verificar GitHub sin autorización de lectura.')
    url='https://api.github.com/repos/SanLean17/parque-movil-ftr'+('/'+path if path else '')
    request=Request(url,headers={'Accept':'application/vnd.github+json','Authorization':'Bearer '+token,'User-Agent':'FTR-schedule-health'})
    try:
        with urlopen(request,timeout=20) as response:return json.load(response)
    except Exception:raise ValueError('No se pudo verificar la agenda en GitHub. Revisá permisos y disponibilidad; no se confirma su activación.') from None


def inspect(config,extra,revision,get):
    result=dict(status='unknown',checked_utc=datetime.now(timezone.utc).isoformat(),revision=revision,workflows={})
    try:
        result['default_branch']=get('')['default_branch']
        for name in WORKFLOWS:
            row=get('actions/workflows/'+name)
            result['workflows'][name]=dict(state=row['state'],url=row.get('html_url'))
        def content(path):return base64.b64decode(get('contents/'+path+'?ref='+revision)['content']).decode('utf-8-sig').replace('\r\n','\n')
        result['cron_verified']=content(native_schedule.PATH)==native_schedule.render(config)
        result['oneoff_verified']=content(oneoff.WORKFLOW)==oneoff.render(extra)
        result['recovery_verified']=content(native_schedule.RECOVERY_PATH)==native_schedule.render_recovery()
        events=[]
        for name in ('actualizar_parques.yml','ftr_recuperar_turnos.yml'):
            rows=get('actions/workflows/'+name+'/runs?event=schedule&branch=main&per_page=1').get('workflow_runs',[])
            for row in rows:events.append({k:row.get(k) for k in ('id','status','conclusion','created_at','run_started_at','html_url')})
        result['last_scheduled']=max(events,key=lambda row:row['created_at']) if events else None
        required=['ftr_sincronizar.yml','ftr_recuperar_turnos.yml']
        if any(config[k]['enabled'] for k in ('drive','cnrt')):required.append('actualizar_parques.yml')
        if extra.get('pending'):required.append('ftr_extraordinarias.yml')
        result['status']=('mismatch' if result['default_branch']!='main' or not all(result[k] for k in ('cron_verified','oneoff_verified','recovery_verified')) else
                          'disabled' if any(result['workflows'][n]['state']!='active' for n in required) else 'active')
    except Exception:
        result['message']='No se pudo comprobar la programación real en GitHub. Revisá permisos o conexión.'
    return result


def confirm(root,config,revision):
    """La confirmación de guardado verifica commit, YAML y workflow activo."""
    if not os.environ.get('GITHUB_TOKEN'):return  # Entornos locales simulados; el workflow siempre lo proporciona.
    if not re.fullmatch('[0-9a-f]{40}',revision):raise ValueError('GitHub no confirmó una revisión válida.')
    result=inspect(config,oneoff.load(root),revision,github_get)
    if result['status']!='active':
        raise ValueError('La configuración quedó guardada, pero GitHub no confirmó la programación activa. Revisá el estado de los workflows y sus permisos; no se informa como activación exitosa.')
    return result


def event_created():
    value=os.environ.get('FTR_EVENT_CREATED_UTC')
    if value:return value
    run_id=os.environ.get('GITHUB_RUN_ID','')
    if not os.environ.get('GITHUB_TOKEN') or not re.fullmatch(r'\d+',run_id):return None
    return github_get('actions/runs/'+run_id).get('created_at')
