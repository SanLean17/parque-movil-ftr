"""Cabeceras reales, navegación y fechas, sin ejecutar fuentes."""
import hashlib,json,os,sys
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from _ftr_runtime.browser_statistics import fixture
from _ftr_runtime.statistics_archive import encoded,entry

def main():
    data=fixture();stats={f'estadisticas/{y}.json':encoded(d) for y,d in data.items()}
    idx=encoded(dict(version=1,periodos=[entry(data[y],stats[f'estadisticas/{y}.json']) for y in sorted(data,reverse=True)]))
    stats['estadisticas/indice.json']=idx
    stats.update({name:b'2026-10-22T20:01:00+00:00\n' for name in ('ultima_actualizacion_parque.txt','ultima_actualizacion_controlados.txt')})
    manifest=dict(period=2027,lines=[r['line'] for r in json.loads((ROOT/'_ftr_config.json').read_bytes())['lines'] if r['enabled']],files_sha256={p:hashlib.sha256(b).hexdigest() for p,b in stats.items()})
    with sync_playwright() as p:
        options=dict(headless=True)
        if os.environ.get('FTR_TEST_BROWSER'):options['executable_path']=os.environ['FTR_TEST_BROWSER']
        browser=p.chromium.launch(**options)
        for width in (320,390,430,768,1280,1440):
            context=browser.new_context(viewport=dict(width=width,height=900));page=context.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def route(r):
                u=urlparse(r.request.url);name=u.path.lstrip('/')
                if u.hostname!='ftr.test':r.continue_();return
                if name=='ftr_publicacion.json':r.fulfill(json=manifest)
                elif name in stats:r.fulfill(body=stats[name])
                elif name in ('index.html','linea.html','estadisticas.html','ftr-estadisticas.css','ftr-estadisticas.js','ftr-navegacion.css','ftr-datos.js','ftr-publica.js','ftr-historial.js','ftr-historial-publico.js'):r.fulfill(path=str(ROOT/name))
                else:r.fulfill(status=404,body='Fuente ficticia ausente')
            context.route('**/*',route)
            for file in ('index.html','linea.html?id=2','estadisticas.html'):
                page.goto('https://ftr.test/'+file);page.wait_for_load_state('networkidle')
                for theme in ('light','dark'):
                    page.evaluate('(t)=>document.documentElement.classList.toggle("dark",t==="dark")',theme)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(file,width,theme)
                    for selector in ('.ftr-brand','.ftr-statistics-link','.ftr-header-actions button'):
                        node=page.locator(selector);assert node.is_visible()
                        box=node.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width
                    link=page.locator('.ftr-statistics-link')
                    assert link.bounding_box()['height']>=44
                    assert page.locator('.ftr-header-actions button').bounding_box()['height']>=44
                    page.locator('.ftr-brand').focus();assert page.locator('.ftr-brand').evaluate('n=>getComputedStyle(n).outlineStyle')!='none'
                    output=os.environ.get('FTR_NAV_SCREENSHOTS')
                    if output and width in (390,1280):
                        folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
                        page.screenshot(path=str(folder/f'cabecera-{file.split(".")[0]}-{width}-{theme}.png'),full_page=True,animations='disabled')
                page.locator('.ftr-statistics-link').click()
                page.wait_for_selector('main[data-status=ready]')
                page.locator('#periodSelect').select_option('2025')
                page.wait_for_function('document.querySelector("#footerPeriod").textContent.includes("2025")')
                assert '2025' in page.locator('#lastRead').inner_text()
                page.wait_for_function('document.querySelector("#fechaParque").textContent.includes("17:01")')
                assert '2026' in page.locator('#fechaParque').inner_text()
                page.locator('.ftr-brand').click();page.wait_for_url('**/index.html')
            assert not errors,errors
            context.close();print(f'Navegación pública {width}px: tres páginas, dos temas, teclado y fechas históricas separadas OK.')
        browser.close()
if __name__=='__main__':main()
