"""Proyecta un informe YA generado y su historial publicado; nunca lee fuentes.

Uso: python _ftr_tools/bootstrap_statistics.py /ruta/al/artefacto.zip
Solo abre resumen.json. No descifra informes ni lee claves privadas.
"""
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from _ftr_runtime.config import load, enabled
from _ftr_runtime.public_statistics import build, write


def bootstrap(archive, root=ROOT):
    config=load(root)
    state=json.loads((root/'_ftr_estado.json').read_text(encoding='utf-8'))
    manifest=json.loads((root/'ftr_publicacion.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(archive) as z:
        report=json.loads(z.read('resumen.json'))
    read=report['inicio_lectura_utc']
    if read!=state['drive']['read_utc'] or report['periodo']!=state['drive']['period'] or state['publication']['status']!='success':
        raise ValueError('El informe no coincide con la lectura publicada.')
    events=[]
    def published(path):
        content=subprocess.check_output(['git','show','HEAD:'+path],cwd=root)
        if hashlib.sha256(content).hexdigest()!=manifest['files_sha256'].get(path):
            raise ValueError('Archivo histórico no verificado.')
        return content
    for line in enabled(config):
        history=json.loads(published(f'historial/linea{line}.json'))
        if history['periodo']!=config['period'] or history['linea']!=line or history['lectura_planilla_utc']!=read or hashlib.sha256(published(f'controlados/linea{line}.csv')).hexdigest()!=history['controles_sha256']:
            raise ValueError('Historial de otra lectura.')
        events.extend(dict(linea=line,dominio=r['dominio'],fecha=date.fromisoformat(r['fecha'])) for r in history['controles'])
    data,_=build(report,events,config,read,pending_mechanics=True)
    write(root,data)
    print(json.dumps(dict(lectura=read,totales=data['totales'],destacados=data['destacados'],anomalias='pendientes; no disponibles en los archivos publicados'),ensure_ascii=False))


if __name__=='__main__':bootstrap(Path(sys.argv[1]))
