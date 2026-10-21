"""Prueba del binario nuevo con plantilla mínima, no del diseño 06.3 ausente."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _ftr_runtime.config import load, digest


def main():
    from playwright.sync_api import sync_playwright
    executable = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='ftr-binario-') as temporary:
        root = Path(temporary)
        # El binario usa una carpeta de datos aislada en --browser-test.
        template = executable.parent/'panel.html'
        if template.exists():
            raise ValueError('La prueba mínima no puede sobrescribir una interfaz existente.')
        template.write_text('<html><body><p id="status">Prueba interna</p><script>window.csrf="__FTR_CSRF__";</script></body></html>',encoding='utf-8')
        process = None
        try:
            tested = subprocess.run([str(executable), '--self-test'], timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
            assert tested.returncode == 0
            assert (executable.parent/'self-test-ok.txt').is_file()
            target = root/'bootstrap.json'
            process = subprocess.Popen([str(executable), '--browser-test', str(target)],
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
            deadline = time.monotonic()+60
            while not target.exists():
                if process.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError('El binario no inició la sesión local.')
                time.sleep(.1)
            with sync_playwright() as p:
                import os
                options = dict(headless=True)
                if os.environ.get('FTR_TEST_BROWSER'):
                    options['executable_path'] = os.environ['FTR_TEST_BROWSER']
                browser = p.chromium.launch(**options)
                context = browser.new_context()
                page = context.new_page()
                requests = []
                page.on('request', lambda r: requests.append(r.url.split('/')[2]))
                page.goto(json.loads(target.read_text())['url'])
                def api(path, payload=None):
                    return page.evaluate('''async ({path,payload}) => {
                      const r=await fetch(path,{method:payload?'POST':'GET',headers:{'Content-Type':'application/json','X-FTR-CSRF':window.csrf},body:payload?JSON.stringify(payload):undefined});
                      return {status:r.status,data:await r.json()};
                    }''',dict(path=path,payload=payload))
                assert api('/api/bootstrap')['data']['version']=='06.3.1'
                assert page.evaluate("fetch('/api/orders').then(r=>r.status)")==403
                config=load(ROOT)
                order=api('/api/submit',dict(action='drive',expected=digest(config)))
                assert order['status']==200 and order['data']['queued']
                identifier=order['data']['request_id']
                page.reload()
                assert api('/api/orders')['data']['orders'][0]['id']==identifier
                duplicate=api('/api/submit',dict(action='drive',expected=digest(config)))
                assert duplicate['data']['request_id']==identifier
                assert api('/api/orders/cancel',dict(request_id=identifier))['status']==200
                assert api('/api/orders')['data']['orders'][0]['status']=='cancelled'
                assert all(host.startswith('127.0.0.1:') for host in requests)
                assert api('/api/quit',{})['status']==200
                context.close();browser.close()
            process.wait(timeout=10)
            assert process.returncode==0
            print('Binario 06.3.1 Windows: inicio, sesión, cola persistente, doble envío, cancelación y cierre OK. Plantilla mínima; sin fuentes reales.')
        finally:
            if process and process.poll() is None:
                process.terminate();process.wait(timeout=10)
            template.unlink(missing_ok=True)


if __name__=='__main__':
    main()
