"""Prueba real del binario Windows y del HTML público, sin credenciales ni fuentes.
No imprime URL de inicio, cookies, CSRF ni contenido laboral. Usa solo datos ficticios.
"""
import json
import re
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
TEMPLATE='''<!doctype html><html lang="es"><meta charset="utf-8"><title>FTR prueba de inicio</title><body><h1>Prueba de inicio</h1><p id="status">Iniciando</p><script>
window.csrf='__FTR_CSRF__';
fetch('/api/bootstrap',{headers:{'X-FTR-CSRF':window.csrf}}).then(r=>r.json()).then(x=>{window.startupResult=x;document.querySelector('#status').textContent='Inicio correcto '+x.version;});
</script></body></html>'''


def launch(executable, destination):
    p=subprocess.Popen([str(executable),'--browser-test',str(destination)])
    deadline=time.monotonic()+40
    while not destination.exists():
        if p.poll() is not None:raise RuntimeError('El ejecutable cerró antes de iniciar.')
        if time.monotonic()>deadline:
            p.terminate();raise RuntimeError('El ejecutable no completó su inicio.')
        time.sleep(.15)
    value=json.loads(destination.read_text(encoding='utf-8'))
    return p,value['url']


def test_executable(browser):
    (DIST/'panel.html').write_text(TEMPLATE,encoding='utf-8')
    processes=[]
    with tempfile.TemporaryDirectory(prefix='ftr-browser-') as tmp:
        context=browser.new_context()
        try:
            for index in range(2):
                print('Prueba de inicio de instancia',index+1)
                p,url=launch(DIST/'FTR_Administracion.exe',Path(tmp)/f'bootstrap{index}.json')
                processes.append(p)
                page=context.new_page()
                response=page.goto(url,wait_until='load')
                assert response.status==200
                page.wait_for_function("window.startupResult && window.startupResult.version === '06.1'")
                assert page.url.endswith('/') and '/iniciar/' not in page.url
                assert page.locator('#status').inner_text()=='Inicio correcto 06.1'
                result=page.evaluate("async()=>({noCsrf:(await fetch('/api/status')).status, foreign:(await fetch('/api/draft',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).status})")
                assert result=={'noCsrf':403,'foreign':403}
                print('Navegación y API de instancia',index+1,'OK')
            ports={page.url for page in context.pages}
            assert len(ports)==2
            for page in context.pages:
                page.reload(wait_until='load')
                page.wait_for_function("window.startupResult && window.startupResult.version === '06.1'")
            cookies=context.cookies()
            names={c['name'] for c in cookies if c['name'].startswith('ftr_')}
            assert len(names)==2
            assert all(c['httpOnly'] and c['sameSite']=='Strict' for c in cookies)
            for page in context.pages:
                status=page.evaluate("async()=> (await fetch('/api/quit',{method:'POST',headers:{'X-FTR-CSRF':window.csrf,'Content-Type':'application/json'},body:'{}'})).status")
                assert status==200
            print('Sesiones independientes y cierre OK')
        finally:
            context.close()
            for p in processes:
                if p.poll() is None:p.terminate()
                p.wait(timeout=10)


def test_web(browser):
    html=(ROOT/'linea.html').read_text(encoding='utf-8')
    extension=(ROOT/'ftr-publica.js').read_text(encoding='utf-8')
    html=re.sub(r'<script\b[^>]*\bsrc=["\'][^"\']+["\'][^>]*>\s*</script>','',html,flags=re.I)
    html=re.sub(r'<link\b[^>]*>','',html,flags=re.I)
    fixture='''<script>
window.tailwind={}; window.Papa={parse:function(url,o){o.complete({data:url.startsWith('controlados/')?[{linea:'37',fecha:'2026-01-02 00:00:00',dominio:'ABC123',interno:'1'},{linea:'37',fecha:'04/02/2026',dominio:'AA123BB',interno:'3'}]:[{dominio:'ABC123',interno:'1',linea:'37'},{dominio:'DEF456',interno:'2',linea:'37'},{dominio:'AA123BB',interno:'3',linea:'37'}]});}};
Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async function(t){window.copiedText=t;}}});
</script>'''
    html=html.replace('<head>','<head>'+fixture).replace('</body>','<script>'+extension+'</script></body>')
    for width in (1440,390):
        for dark in (False,True):
            print('Prueba web',width,'oscuro' if dark else 'claro')
            context=browser.new_context(viewport={'width':width,'height':900})
            context.route('**/*',lambda route: route.fulfill(status=200,content_type='text/html',body=html) if route.request.resource_type=='document' else route.abort())
            page=context.new_page();dialogs=[]
            def dialog(d):
                dialogs.append({'type':d.type,'message':d.message});d.accept()
            page.on('dialog',dialog)
            page.goto('https://ftr.test/linea.html?id=37')
            if dark:page.evaluate("document.documentElement.classList.add('dark')")
            assert page.locator('#countControlados').inner_text().strip()=='2'
            order=page.locator('button[onclick="copyControlled()"],button[onclick="copyMissing()"]').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("onclick"))')
            assert order==['copyControlled()','copyMissing()']
            page.locator('button[onclick="copyControlled()"]').click()
            assert dialogs[-1]['type']=='alert'
            assert dialogs[-1]['message']=='¡Copiado al portapapeles!\n\n'+page.evaluate('window.copiedText')
            assert 'ABC123' in dialogs[-1]['message'] and 'AA123BB' in dialogs[-1]['message']
            assert '02/01/2026' in dialogs[-1]['message'] and '00:00:00' not in dialogs[-1]['message']
            page.locator('button[onclick="copyMissing()"]').click()
            assert dialogs[-1]['type']=='alert'
            assert dialogs[-1]['message']=='¡Copiado al portapapeles!\n\n'+page.evaluate('window.copiedText')
            assert 'DEF456' in dialogs[-1]['message'] and 'ABC123' not in dialogs[-1]['message']
            page.evaluate("setFilter('CONTROLADO')")
            assert page.locator('#fleetTbody').get_attribute('data-view')=='CONTROLADO'
            page.evaluate("setFilter('ALL')")
            assert page.locator('#fleetTbody').get_attribute('data-view')=='ALL'
            page.evaluate("()=>{navigator.clipboard.writeText=async()=>{throw new Error('prueba');};}")
            page.locator('button[onclick="copyControlled()"]').click()
            assert dialogs[-1]['type']=='prompt'
            context.close()


def main():
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            test_executable(browser)
            test_web(browser)
            browser.close()
        result={'version':'06.1','compiled_windows_startup':'OK','two_instances_same_browser':'OK','session_cookie_csrf':'OK','copy_alerts_desktop_mobile_light_dark':'OK','private_sources_used':False,'bots_executed':False}
        (DIST/'COMPROBACION_NAVEGADOR.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Inicio HTTP del ejecutable y sesión en Chromium: OK. Avisos y orden de botones (4 vistas): OK. Sin credenciales ni lectura de fuentes.')
    except Exception as exc:
        positions=[f'{Path(f.filename).name}:{f.lineno}' for f in traceback.extract_tb(exc.__traceback__) if Path(f.filename).name=='browser_smoke061.py']
        categories=re.findall(r'(?:net::ERR_[A-Z_]+|SyntaxError|TypeError|ReferenceError|SecurityError)',str(exc))
        print('Prueba no completada:',type(exc).__name__,'posiciones',','.join(positions),'categorias',','.join(categories))
        raise SystemExit(1) from None

if __name__=='__main__':main()
