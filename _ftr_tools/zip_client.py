"""ZIP de una carpeta completa, después de probar su ejecutable."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from package_client import release, VERSION, DIRECTORY

def main():
    release()
    folder=Path(sys.argv[1]).resolve()
    assert folder.name==DIRECTORY
    assert json.loads((folder/'VERSION.json').read_text(encoding='utf-8'))['version']==VERSION
    expected={}
    for line in (folder/'SHA256_ARCHIVOS.txt').read_text().splitlines():
        digest,name=line.split('  ',1);expected[name]=digest
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
    assert set(p.name for p in folder.iterdir())==set(expected)|{'SHA256_ARCHIVOS.txt'}
    target=folder.with_suffix('.zip')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(folder.iterdir()):archive.write(path,folder.name+'/'+path.name)
    with zipfile.ZipFile(target) as archive:assert archive.testzip() is None
    print(target.name+': carpeta completa, integridad correcta, sin archivos adicionales.')

if __name__=='__main__':main()
