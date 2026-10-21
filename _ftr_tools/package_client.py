"""Prepara una carpeta completa y verificable. Nunca agrega archivos privados."""
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    executable=Path(sys.argv[1]).resolve()
    target=Path(sys.argv[2]).resolve()
    if not executable.is_file() or target.exists():
        raise ValueError('Se necesita un ejecutable y una carpeta de destino nueva.')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    target.mkdir(parents=True)
    shutil.copyfile(executable,target/'FTR_Administracion.exe')
    for name in ('panel.html','panel-bridge.js'):
        shutil.copyfile(ROOT/'_ftr_app'/name,target/name)
    shutil.copyfile(ROOT/'_ftr_app/LEEME_0631.txt',target/'LEEME_PRIMERO.txt')
    info=dict(version='06.3.1',revision=revision,built_utc=datetime.now(timezone.utc).isoformat(),
              platform='Windows x64',interface='06.3 original; estilos conservados',signed=False,
              private_data_included=False)
    (target/'VERSION.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(target.iterdir())]
    (target/'SHA256_ARCHIVOS.txt').write_text('\n'.join(hashes)+'\n',encoding='utf-8')
    print('Carpeta completa 06.3.1 preparada; cinco archivos comprobables y listado de integridad.')


if __name__=='__main__':main()
