"""Prepara una carpeta completa y verificable. Nunca agrega archivos privados."""
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from _ftr_app.version import VERSION, DIRECTORY


def release():
    info=json.loads((ROOT/'_ftr_app/windows-release.json').read_text(encoding='utf-8'))
    if info['version']!=VERSION or info['distribution']!=DIRECTORY:
        raise ValueError('Marcador de entrega y programa no coinciden.')
    if VERSION not in (ROOT/'_ftr_app/panel.html').read_text(encoding='utf-8'):
        raise ValueError('Interfaz de otra versión.')
    return info


def main():
    release()
    if sys.argv[1]=='--version-file':
        version=tuple(map(int,VERSION.split('.')))+(0,)
        target=Path(sys.argv[2]);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text("VSVersionInfo(ffi=FixedFileInfo(filevers="+repr(version)+",prodvers="+repr(version)+",mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[StringStruct('FileDescription','FTR Administración'),StringStruct('FileVersion','"+VERSION+"'),StringStruct('ProductVersion','"+VERSION+"'),StringStruct('ProductName','FTR Administración')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])",encoding='utf-8')
        return
    executable=Path(sys.argv[1]).resolve()
    target=Path(sys.argv[2]).resolve()
    if not executable.is_file() or target.exists():
        raise ValueError('Se necesita un ejecutable y una carpeta de destino nueva.')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    target.mkdir(parents=True)
    shutil.copyfile(executable,target/'FTR_Administracion.exe')
    for name in ('panel.html','panel-bridge.js','panel-history.js','panel-statistics-admin.js'):
        shutil.copyfile(ROOT/'_ftr_app'/name,target/name)
    shutil.copyfile(ROOT/'ftr-historial.js',target/'ftr-historial.js')
    shutil.copyfile(ROOT/'_ftr_app/LEEME_0631.txt',target/'LEEME_PRIMERO.txt')
    shutil.copyfile(ROOT/'_ftr_app/DICCIONARIO_TECNICO.txt',target/'DICCIONARIO_TECNICO.txt')
    info=dict(version=VERSION,revision=revision,built_utc=datetime.now(timezone.utc).isoformat(),
              platform='Windows x64',interface='06.3 original; estilos conservados',signed=False,
              private_data_included=False)
    (target/'VERSION.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(target.iterdir())]
    (target/'SHA256_ARCHIVOS.txt').write_text('\n'.join(hashes)+'\n',encoding='utf-8')
    print('Carpeta completa '+VERSION+' preparada y verificada contra el marcador de entrega.')


if __name__=='__main__':main()
