"""Sella los archivos preparados en Git sin cambiar fechas de lectura ni datos.

Uso de mantenimiento, no lee fuentes. Las huellas usan los bytes de Git para
evitar diferencias CRLF/LF de un checkout Windows. Después se agrega el manifiesto.
"""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    def staged(name):
        return subprocess.check_output(['git','show',':'+name],cwd=ROOT)
    config=json.loads(staged('_ftr_config.json'))
    manifest=json.loads(staged('ftr_publicacion.json'))
    paths=['index.html','linea.html','ftr-publica.js','ftr-datos.js',
           'ultima_actualizacion_parque.txt','ultima_actualizacion_controlados.txt']
    paths += [f"{folder}/linea{line['line']}.csv" for folder in ('parques','controlados') for line in config['lines'] if line['enabled']]
    manifest['files_sha256']={path:hashlib.sha256(staged(path)).hexdigest() for path in paths}
    (ROOT/'ftr_publicacion.json').write_text(json.dumps(manifest)+'\n',encoding='utf-8',newline='\n')
    print(f'Huellas verificables de {len(paths)} archivos. Fechas de lectura conservadas.')


if __name__=='__main__':main()
