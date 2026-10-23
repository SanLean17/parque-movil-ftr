"""La validación del motor no crea una nueva distribución del administrador."""
import json
import os
import re
import subprocess
from pathlib import Path


def needs_package(paths):
    return any(p.startswith(('_ftr_app/','_ftr_panel/')) or p in (
        '_ftr_tools/package_client.py','_ftr_tools/check_client_build.py') for p in paths)


def main():
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
    pr=event.get('pull_request')
    base=pr['base']['sha'] if pr else event.get('before','')
    head=pr['head']['sha'] if pr else os.environ['GITHUB_SHA']
    if not all(re.fullmatch('[a-f0-9]{40}',v or '') for v in (base,head)):
        raise ValueError('No se pudo determinar el alcance del cliente Windows.')
    if base=='0'*40:
        paths=subprocess.check_output(['git','ls-tree','--name-only','-r',head],text=True).splitlines()
    else:
        paths=subprocess.check_output(['git','diff','--name-only',base,head],text=True).splitlines()
    with Path(os.environ['GITHUB_OUTPUT']).open('a',encoding='utf-8') as out:
        out.write('package='+str(needs_package(paths)).lower()+'\n')
    print('Se compila el administrador.' if needs_package(paths) else 'Se valida sin generar paquete Windows: el cliente no cambió.')


if __name__=='__main__':main()
