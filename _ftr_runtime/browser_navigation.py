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
            context=browser.new_context(viewport=dict(width=width,height=900),timezone_id='Asia/Tokyo');page=context.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def route(r):
                u=urlparse(r.request.url);name=u.path.lstrip('/')
                if u.hostname!='ftr.test':r.continue_();return
                if name=='ftr_publicacion.json':r.fulfill(json=manifest)
                elif name in stats:r.fulfill(body=stats[name])
                elif name in ('index.html','linea.html','estadisticas.html','ftr-estadisticas.css','ftr-estadisticas.js','ftr-navegacion.css','ftr-datos.js','ftr-publica.js','ftr-historial.js','ftr-historial-publico.js'):r.fulfill(path=str(ROOT/name))
                else:r.fulfill(status=404,body='Fuente ficticia ausente')
            context.route('**/*',route)
            date_styles={}
            expected=['Última actualización de parque móvil realizada el 22/10/2026 a las 17:01 hs.','Última actualización de unidades controladas realizada el 22/10/2026 a las 17:01 hs.']
            for file in ('index.html','linea.html?id=2','estadisticas.html'):
                page.goto('https://ftr.test/'+file);page.wait_for_load_state('networkidle')
                for theme in ('light','dark'):
                    page.evaluate('(t)=>document.documentElement.classList.toggle("dark",t==="dark")',theme)
                    overflow=page.evaluate('''()=>Array.from(document.querySelectorAll('body *')).filter(n=>{const r=n.getBoundingClientRect();return r.width&&r.right>innerWidth+1&&getComputedStyle(n).position!=="absolute"}).slice(0,12).map(n=>({tag:n.tagName,cls:n.className,right:n.getBoundingClientRect().right,text:n.textContent.slice(0,70)}))''')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(file,width,theme,overflow)
                    for selector in ('.ftr-brand','.ftr-statistics-link','.ftr-header-actions button'):
                        node=page.locator(selector);assert node.is_visible()
                        box=node.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width
                    if file in ('index.html','estadisticas.html'):
                        assert page.locator('.ftr-update-dates>div').all_inner_texts()==expected,(file,page.locator('.ftr-update-dates>div').all_inner_texts(),errors)
                        assert page.locator('.ftr-update-dates').inner_text().count('Última actualización')==2
                        assert 'FUENTES OPERATIVAS ACTUALES' not in page.locator('body').inner_text()
                        styles=page.locator('.ftr-update-dates').evaluate('(n)=>{const s=getComputedStyle(n);return [s.fontFamily,s.fontSize,s.lineHeight,s.color,s.padding,s.marginTop]}')
                        if file=='index.html':date_styles[theme]=styles
                        else:assert styles==date_styles[theme],(styles,date_styles[theme])
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
                assert page.locator('.ftr-update-dates>div').all_inner_texts()==expected,(file,page.locator('.ftr-update-dates>div').all_inner_texts(),errors)
                page.locator('.ftr-brand').click();page.wait_for_url('**/index.html')
            for file in ('index.html','estadisticas.html'):
                context.route('**/ultima_actualizacion_*.txt*',lambda r:r.fulfill(status=404,body='Ausente'))
                page.goto('https://ftr.test/'+file);page.wait_for_load_state('networkidle')
                assert page.locator('.ftr-update-dates>div').all_inner_texts()==[t.split(' realizada el ')[0]+' realizada el -' for t in expected]
            assert not errors,errors
            context.close();print(f'Navegación pública {width}px: tres páginas, dos temas, teclado y fechas históricas separadas OK.')
        browser.close()
if __name__=='__main__':main()
