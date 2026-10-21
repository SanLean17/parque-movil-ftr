"""Recupera la publicación de datos ya guardados sin volver a leer fuentes."""
import json
import subprocess
from pathlib import Path

STATE='_ftr_estado.json'


def pending(state):return state.get('publication',{}).get('status') in ('pending','error')


def verify(root,state,revision,commit,build,stamp):
    publication=state.setdefault('publication',{})
    publication.update(status='pending',revision=revision,attempt_utc=stamp(),attempts=publication.get('attempts',0)+1)
    error=None
    try:
        build(revision)
        publication.update(status='success',verified_utc=stamp(),error=None)
    except Exception as exc:
        publication.update(status='error',error='La publicación no quedó verificada. Se reintentará publicar los datos guardados sin volver a leer las fuentes.')
        error=exc
    (Path(root)/STATE).write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    commit(root,[STATE])
    if error:raise error


def current_revision(root):
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
