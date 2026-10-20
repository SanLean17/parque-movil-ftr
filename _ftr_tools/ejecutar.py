"""Entrada del coordinador con errores de Git identificables y sin secretos."""
from pathlib import Path
import os
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from _ftr_runtime import worker


def commit_validated(root, paths):
    def git(*args):
        result=subprocess.run(['git',*args],cwd=root,text=True,capture_output=True)
        if result.returncode:
            detail=result.stderr[:1800]
            for name in ('GITHUB_TOKEN','GOOGLE_SERVICE_ACCOUNT_JSON'):
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
    git('push','origin','HEAD:main')
    return git('rev-parse','HEAD')


if __name__=='__main__':
    worker.commit=commit_validated
    sys.exit(worker.main())
