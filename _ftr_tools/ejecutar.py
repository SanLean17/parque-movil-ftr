"""Coordinador: agenda auditable y publicación con errores de Git identificables."""
from pathlib import Path
import os
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from _ftr_runtime import worker
from _ftr_runtime import agenda
from _ftr_runtime import native_schedule


def commit_validated(root, paths):
    paths = list(paths)
    calendar_changed = False
    if os.environ.get('FTR_ACTION') == 'config':
        calendar_changed = native_schedule.stage(root, worker.load(root))
        if calendar_changed and native_schedule.PATH not in paths:
            paths.append(native_schedule.PATH)
    def git(*args):
        result=subprocess.run(['git',*args],cwd=root,text=True,capture_output=True)
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
    git('commit','-m','FTR: datos y configuración validados')
    if calendar_changed:
        native_schedule.push(root)
    else:
        git('push','origin','HEAD:main')
    return git('rev-parse','HEAD')


_original_plan = worker.plan

def audited_plan():
    mode, config, state, jobs = _original_plan()
    moment = worker.now()
    if mode == 'config':
        native_schedule.preflight(worker.ROOT, config)
        agenda.activate_changed_schedules(worker.load(worker.ROOT), config, state, moment)
    if os.environ.get('FTR_PHASE') == 'check':
        text = agenda.explain(config, state, moment, jobs, mode)
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
