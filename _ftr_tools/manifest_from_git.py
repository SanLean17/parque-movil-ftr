"""Sella los archivos preparados en Git sin cambiar fechas de lectura ni datos.

Uso de mantenimiento, no lee fuentes. Las huellas usan los bytes de Git para
evitar diferencias CRLF/LF de un checkout Windows. Después se agrega el manifiesto.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _ftr_runtime.public_statistics import ASSETS


def main():
    def staged(name):
        return subprocess.check_output(['git','show',':'+name],cwd=ROOT)
    config=json.loads(staged('_ftr_config.json'))
    manifest=json.loads(staged('ftr_publicacion.json'))
    paths=['index.html','linea.html','ftr-publica.js','ftr-datos.js','ftr-historial.js','ftr-historial-publico.js',
           'ultima_actualizacion_parque.txt','ultima_actualizacion_controlados.txt']
    paths += [f"{folder}/linea{line['line']}.csv" for folder in ('parques','controlados') for line in config['lines'] if line['enabled']]
    tracked=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines())
    paths += [name for name in ASSETS if name in tracked]
    paths += [f"historial/linea{line['line']}.json" for line in config['lines'] if line['enabled'] and f"historial/linea{line['line']}.json" in tracked]
    manifest['files_sha256']={path:hashlib.sha256(staged(path)).hexdigest() for path in paths}
    (ROOT/'ftr_publicacion.json').write_text(json.dumps(manifest)+'\n',encoding='utf-8',newline='\n')
    print(f'Huellas verificables de {len(paths)} archivos. Fechas de lectura conservadas.')


if __name__=='__main__':main()
