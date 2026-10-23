"""Inicio, UI original recuperada, cola y cierre del paquete Windows completo."""
import json
import hashlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'_ftr_app'))
import os
import shutil
from _ftr_app.version import VERSION
from _ftr_runtime.config import load, digest


def main():
    from playwright.sync_api import sync_playwright
    executable = Path(sys.argv[1]).resolve()
    import pefile
    with pefile.PE(str(executable)) as pe:
        fixed=pe.VS_FIXEDFILEINFO[0]
        actual=(fixed.FileVersionMS>>16,fixed.FileVersionMS&65535,fixed.FileVersionLS>>16)
        assert actual==tuple(map(int,VERSION.split('.')))
    assert json.loads((executable.parent/'VERSION.json').read_text(encoding='utf-8'))['version']==VERSION
    with tempfile.TemporaryDirectory(prefix='ftr-binario-') as temporary:
        root = Path(temporary)
        template = executable.parent/'panel.html'
        assert template.is_file() and (executable.parent/'panel-bridge.js').is_file()
        for line in (executable.parent/'SHA256_ARCHIVOS.txt').read_text().splitlines():
            expected,name=line.split('  ',1)
            assert hashlib.sha256((executable.parent/name).read_bytes()).hexdigest()==expected,name
        process = None
        try:
            tested = subprocess.run([str(executable), '--self-test'], timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
            assert tested.returncode == 0
            assert (executable.parent/'self-test-ok.txt').is_file()
            assert (executable.parent/'self-test-ok.txt').read_text(encoding='utf-8').startswith(VERSION+':')
            target = root/'bootstrap.json'
            process = subprocess.Popen([str(executable), '--browser-test', str(target)],
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
            deadline = time.monotonic()+60
            while not target.exists():
                if process.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError('El binario no inició la sesión local.')
                time.sleep(.1)
            with sync_playwright() as p:
                options = dict(headless=True)
                if os.environ.get('FTR_TEST_BROWSER'):
                    options['executable_path'] = os.environ['FTR_TEST_BROWSER']
                browser = p.chromium.launch(**options)
                context = browser.new_context()
                page = context.new_page()
                requests = []
                page.on('request', lambda r: requests.append(r.url.split('/')[2]))
                config=load(ROOT)
                def bootstrap(route):
                    response=route.fetch();value=response.json()
                    assert value['version']=='06.3.7' and not value['connected']
                    value['remote']={'config':config,'digest':digest(config),'state':{},'oneoffs':{'version':1,'pending':{},'history':[]}}
                    route.fulfill(response=response,json=value)
                page.route('**/api/bootstrap',bootstrap)
                page.goto(json.loads(target.read_text())['url'])
                page.wait_for_selector('html[data-ready="true"]')
                from history_browser_checks import check_admin_history
                check_admin_history(page)
                def api(path, payload=None):
                    return page.evaluate('''async ({path,payload}) => {
                      const r=await fetch(path,{method:payload?'POST':'GET',headers:{'Content-Type':'application/json', 'X-FTR-CSRF':document.querySelector('meta[name="ftr-csrf"]').content},body:payload?JSON.stringify(payload):undefined});
                      return {status:r.status,data:await r.json()};
                    }''',dict(path=path,payload=payload))
                assert api('/api/bootstrap')['data']['version']=='06.3.7'
                assert page.evaluate("fetch('/api/orders').then(r=>r.status)")==403
                order=api('/api/submit',dict(action='drive',expected=digest(config)))
                assert order['status']==200 and order['data']['queued']
                identifier=order['data']['request_id']
                page.reload()
                page.wait_for_selector('html[data-ready="true"]')
                assert 'Pendiente de envío' in page.locator('#cloudActivity').inner_text()
                assert api('/api/orders')['data']['orders'][0]['id']==identifier
                duplicate=api('/api/submit',dict(action='drive',expected=digest(config)))
                assert duplicate['data']['request_id']==identifier
                page.locator('[data-order-id] button').click()
                page.locator('#dialogConfirm').click()
                page.wait_for_function("() => document.querySelector('#cloudActivity').textContent.includes('Cancelada antes del envío')")
                assert api('/api/orders')['data']['orders'][0]['status']=='cancelled'
                from oneoff_browser_checks import check_oneoff_ui
                check_oneoff_ui(page)
                from recovery_browser_checks import check_recovery_ui
                check_recovery_ui(page)
                from statistics_browser_checks import check_statistics_admin,check_mechanical_review
                check_statistics_admin(page)
                check_mechanical_review(page,root/'perfil-prueba')
                assert page.locator('.nav [data-view]').count()==9
                for view in page.locator('.nav [data-view]').evaluate_all('ns=>ns.map(n=>n.dataset.view)'):
                    page.evaluate('(v)=>showView(v)',view)
                    assert page.locator('[data-page="'+view+'"]').is_visible()
                assert api('/api/preferences',{'theme':'dark'})['status']==200
                assert api('/api/draft',dict(config=config,expected=digest(config)))['status']==200
                pending=api('/api/submit',dict(action='drive',expected=digest(config)))['data']['request_id']
                assert all(host.startswith('127.0.0.1:') for host in requests)
                page.evaluate("showView('connections')")
                page.locator('#quitPanel').click();page.locator('#dialogConfirm').click()
                page.wait_for_function("() => document.body.textContent.includes('Panel cerrado')")
                context.close();browser.close()
            process.wait(timeout=10)
            assert process.returncode==0
            profile=root/'perfil-prueba'
            import server
            # Una autorización ficticia permite comprobar DPAPI sin conectar a GitHub.
            (profile/'github.dpapi').write_bytes(server.protect(b'FTR_FICTICIO_NO_CREDENCIAL'))
            saved={p.name:p.read_bytes() for p in profile.iterdir() if p.is_file()}
            assert 'interpretaciones.dpapi' in saved and 'informe.dpapi' in saved
            assert json.loads(server.protect(saved['interpretaciones.dpapi'],True))['registros']
            relocated=root/'otra-carpeta';shutil.copytree(executable.parent,relocated)
            target.unlink()
            process=subprocess.Popen([str(relocated/executable.name),'--browser-test',str(target)],creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+60
            while not target.exists():
                assert process.poll() is None and time.monotonic()<deadline
                time.sleep(.1)
            with sync_playwright() as p:
                browser=p.chromium.launch(**options);context=browser.new_context();page=context.new_page()
                page.goto(json.loads(target.read_text())['url']);page.wait_for_selector('html[data-ready="true"]')
                boot=api('/api/bootstrap')['data']
                assert boot['version']==VERSION and boot['connected']
                assert boot['preferences']['theme']=='dark' and boot['draft']['config']==config
                assert any(row['id']==pending for row in api('/api/orders')['data']['orders'])
                assert api('/api/statistics-admin')['status']==200
                assert all((profile/name).read_bytes()==data for name,data in saved.items()),'El reinicio alteró el perfil'
                assert api('/api/status')['status']!=200,'El modo de prueba debe bloquear GitHub'
                page.evaluate("showView('connections')");page.locator('#quitPanel').click();page.locator('#dialogConfirm').click()
                page.wait_for_function("() => document.body.textContent.includes('Panel cerrado')")
                context.close();browser.close()
            process.wait(timeout=10);assert process.returncode==0
            print('Paquete completo 06.3.7 Windows: integridad, inicio, UI, sesión, cola, doble envío, cancelación visible y cierre OK. Sin fuentes reales.')
        finally:
            if process and process.poll() is None:
                process.terminate();process.wait(timeout=10)
            (executable.parent/'self-test-ok.txt').unlink(missing_ok=True)


if __name__=='__main__':
    main()
