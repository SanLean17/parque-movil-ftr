"""Coordinador: agenda auditable y publicación con errores de Git identificables."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from _ftr_runtime import worker
from _ftr_runtime import agenda
from _ftr_runtime import native_schedule
from _ftr_runtime import oneoff


def commit_validated(root, paths):
    paths = list(paths)
    calendar_changed = oneoff.WORKFLOW in paths
    if os.environ.get('FTR_ACTION') == 'config':
        recurrent_changed = native_schedule.stage(root, worker.load(root))
        calendar_changed = calendar_changed or recurrent_changed
        if recurrent_changed and native_schedule.PATH not in paths:
            paths.append(native_schedule.PATH)
    def git(*args):
        result=subprocess.run(['git',*args],cwd=root,text=True,encoding='utf-8',errors='replace',capture_output=True)
        if result.returncode:
            detail=result.stderr[:1800]
            for name in ('GITHUB_TOKEN','GOOGLE_SERVICE_ACCOUNT_JSON','FTR_SCHEDULE_TOKEN'):
                value=os.environ.get(name,'')
                if value:detail=detail.replace(value,'[credencial omitida]')
            detail=re.sub(r'https://[^\s/@]+:[^\s/@]+@','https://[credencial omitida]@',detail)
            raise ValueError('No se pudo guardar: git '+args[0]+' (código '+str(result.returncode)+'). '+detail)
        return result.stdout.strip()
    git('config','user.name','github-actions[bot]')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','--',*paths)
    if not git('diff','--cached','--name-only'):
        return git('rev-parse','HEAD')
    message = 'FTR: configuración y calendario guardados' if os.environ.get('FTR_ACTION') == 'config' else 'FTR: resultados de fuentes y estado de ejecución'
    if os.environ.get('FTR_ACTION') in ('oneoff-set','oneoff-cancel'):message='FTR: programación extraordinaria guardada sin leer fuentes'
    git('commit','-m',message)
    if calendar_changed:
        native_schedule.push(root)
    else:
        git('push','origin','HEAD:main')
    return git('rev-parse','HEAD')


def sources_for_execution(mode, config, jobs, event_name, state=None, moment=None):
    """Una llegada real del calendario aprovecha el arranque para leer Drive.

    Política solicitada: una lectura extra, incluso antes del horario principal,
    no sustituye la de ese horario. CNRT conserva su calendario de varios días.
    No se aplica a guardar configuración, consultar estado, push ni solicitudes
    manuales. La agenda pasiva del panel conserva su próximo turno principal.
    """
    result = list(jobs)
    if mode == 'scheduled' and event_name == 'schedule' and config['drive']['enabled']:
        row = (state or {}).get('drive', {})
        if row.get('status') == 'error' and row.get('attempt_utc') and moment:
            from datetime import datetime, timedelta
            try:
                if moment - datetime.fromisoformat(row['attempt_utc']) < timedelta(hours=1):
                    return result
            except (ValueError, TypeError):
                pass
        if 'drive' not in result:
            result.append('drive')
    return result


def cron_origin():
    """Registra el cron que GitHub envió, sin volcar el payload ni credenciales."""
    path = os.environ.get('GITHUB_EVENT_PATH')
    if not path:
        return None
    try:
        with open(path, encoding='utf-8') as stream:
            event = json.load(stream)
        value = event.get('schedule') if isinstance(event, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None
    if isinstance(value, str) and re.fullmatch(r'[0-9* /,\-]{1,80}', value):
        return value
    return None


_original_plan = worker.plan

def audited_plan():
    mode, config, state, jobs = _original_plan()
    moment = worker.now()
    if mode == 'config':
        native_schedule.preflight(worker.ROOT, config)
        agenda.activate_changed_schedules(worker.load(worker.ROOT), config, state, moment)
    event_name = os.environ.get('GITHUB_EVENT_NAME', '')
    jobs = sources_for_execution(mode, config, jobs, event_name, state, moment)
    if os.environ.get('FTR_PHASE') == 'check':
        text = agenda.explain(config, state, moment, jobs, mode)
        if mode == 'scheduled' and event_name == 'schedule':
            origin = cron_origin()
            text += '\nOrigen: evento automático schedule de GitHub.\n'
            text += ('Cron recibido (UTC): `' + origin + '`.\n') if origin else 'El evento no informó una expresión cron legible.\n'
            if 'drive' in jobs:
                text += ('Planilla FTR: se leerá en este arranque automático, aunque el turno principal todavía no haya llegado o ya se haya atendido. '
                         'Una lectura extra no cancela la del horario configurado.\n')
            elif config['drive']['enabled']:
                text += 'Planilla FTR: espera el plazo mínimo de reintento tras el error anterior; no se leerá en este arranque.\n'
            else:
                text += 'Planilla FTR: automatización desactivada; se respeta la pausa.\n'
            text += 'CNRT conserva su intervalo y solo se descarga cuando corresponde.\n'
        print(text)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
                f.write(text)
    return mode, config, state, jobs


def main():
    worker.commit = commit_validated
    worker.selected = agenda.select_jobs
    worker.plan = audited_plan
    return worker.main()


if __name__ == '__main__':
    sys.exit(main())
