"""Prueba móvil/táctil real. Fuentes ficticias; capturas opcionales de agregados guardados."""
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from _ftr_runtime.test_source_pipeline import SourcePipelineTests
from _ftr_runtime.public_statistics import FILE, ASSETS


def fixture():
    test=SourcePipelineTests();test.setUp()
    try:
        rows=[['FECHA','LINEA','DOMINIO','INTERNO','ESTADO','NOVEDADES']]
        for line,n in ((36,100),(37,20)):
            for i in range(n):
                rows.append([f'01/{1+i%10:02}/2026',line,'AA111AA' if line==36 else 'CC333CC',1,
                    'FUERA DE SERVICIO' if i<10 else 'OBSERVADO' if i<15 else 'SIN NOVEDAD',
                    'barra larga; freno trasero derecho; R3' if i<10 else 'sin novedad'])
        test.google([test.sheet('LINEA 36/37',rows)])
        return json.loads((test.root/FILE).read_text())
    finally:test.tearDown()


def main():
    fake=fixture()
    output=Path(os.environ['FTR_STATS_SCREENSHOTS']) if os.environ.get('FTR_STATS_SCREENSHOTS') else None
    if output:output.mkdir(parents=True,exist_ok=True)
    actual=json.loads((ROOT/FILE).read_text(encoding='utf-8'))
    with sync_playwright() as p:
        options=dict(headless=True)
        if os.environ.get('FTR_TEST_BROWSER'):options['executable_path']=os.environ['FTR_TEST_BROWSER']
        browser=p.chromium.launch(**options)
        try:
            for width in (360,390,430,768,1440):
                context=browser.new_context(viewport=dict(width=width,height=900),has_touch=width<800,color_scheme='light')
                page=context.new_page();errors=[];requested=[];current=copy.deepcopy(fake);wrong_hash=False;wrong_period=False
                page.on('pageerror',lambda e:errors.append(str(e)))
                def route(r):
                    u=urlparse(r.request.url);requested.append(r.request.url)
                    if u.hostname!='ftr.test':
                        if u.hostname in ('fonts.googleapis.com','fonts.gstatic.com','cdnjs.cloudflare.com'):r.continue_()
                        else:r.abort()
                        return
                    name=u.path.lstrip('/');payload=json.dumps(current,ensure_ascii=False).encode()
                    if name=='ftr_publicacion.json':r.fulfill(json=dict(period=current['periodo']+(1 if wrong_period else 0),lines=[v['linea'] for v in current['lineas']],files_sha256={FILE:'0'*64 if wrong_hash else hashlib.sha256(payload).hexdigest()}))
                    elif name==FILE:r.fulfill(body=payload,content_type='application/json')
                    elif name in (*ASSETS,'ftr-datos.js'):r.fulfill(path=str(ROOT/name))
                    else:r.fulfill(status=404,body='Sin fuentes')
                context.route('**/*',route)
                def open_page():
                    page.goto('https://ftr.test/estadisticas.html')
                    page.wait_for_selector('main[data-status="ready"]')
                def layout():
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'desborde {width}'
                    assert page.locator('.metric').count()==6
                    assert page.locator('.month').count()==12
                    assert page.locator('.category').count()==5
                    if width<640:
                        boxes=page.locator('.metric').evaluate_all('ns=>ns.map(n=>{let r=n.getBoundingClientRect();return {x:r.x,y:r.y}})')
                        assert boxes[0]['y']==boxes[1]['y'] and boxes[2]['y']>boxes[0]['y']
                    assert page.locator('a[href*="_ftr"],a[href*="linea.html"]').count()==0
                open_page()
                assert page.locator('[data-metric="registros_validos"] .metric-value').inner_text()=='120'
                assert page.locator('[data-metric="unidades_repetidas"] .metric-value').inner_text()=='2'
                for theme in ('light','dark'):
                    if (theme=='dark')!=page.evaluate('document.documentElement.classList.contains("dark")'):page.locator('#themeButton').click()
                    layout();page.locator('[data-month="3"]').click();assert 'MARZO — 12 CONTROLES' in page.locator('#monthSelection').inner_text()
                    page.locator('[data-month="12"]').click();assert 'POSTERIOR' in page.locator('#monthSelection').inner_text()
                    for cat,label in (('direccion','Barra larga'),('frenos','Frenos traseros'),('suspension','Amortiguadores'),('transmision','Cardán'),('otras','Menciones pendientes')):
                        page.locator('[data-category="'+cat+'"]').click();assert label in page.locator('#components').inner_text()
                        assert page.locator('[data-category="'+cat+'"]').get_attribute('aria-pressed')=='true'
                    page.locator('[data-category="direccion"]').focus();page.keyboard.press('Enter');assert page.locator('#componentTitle').inner_text()=='DIRECCIÓN'
                # Poca muestra queda consultable, fuera del ranking principal.
                current=copy.deepcopy(fake);current['minimo_controles_proporcion']=20
                # El fixture de cuatro visitas ejercita los casos sin muestra suficiente.
                from _ftr_runtime.test_public_statistics import StatisticsPipelineTests
                small=StatisticsPipelineTests();small.setUp()
                try:small.google(small.visits());current=small.read()
                finally:small.tearDown()
                open_page();page.locator('#showLines').click();assert page.locator('#smallSamples').is_visible();assert page.locator('#smallRatios .ratio-row').count()==2
                page.locator('#showLines').click();assert page.locator('#smallSamples').is_hidden()
                # Las capturas de entrega usan exclusivamente agregados reales ya guardados.
                current=copy.deepcopy(actual);open_page()
                for theme in ('light','dark'):
                    if (theme=='dark')!=page.evaluate('document.documentElement.classList.contains("dark")'):page.locator('#themeButton').click()
                    layout();assert 'Pendiente' in page.locator('#mechanicsStatus').inner_text()
                    page.locator('[data-category="frenos"]').click();assert page.locator('#components .component-count').all_inner_texts()==['—']*4
                    if output:
                        page.evaluate('window.scrollTo(0,0)')
                        page.evaluate('document.fonts.ready')
                        page.screenshot(path=str(output/f'estadisticas-{width}-{theme}.png'),full_page=True,animations='disabled')
                        if width in (390,1440):page.screenshot(path=str(output/f'vista-{width}-{theme}.png'),animations='disabled')
                # Integridad, período y rechazo de un JSON incoherente, aun con hash válido.
                wrong_hash=True;page.reload();page.wait_for_selector('main[data-status="error"]');assert page.locator('[data-metric="registros_validos"] .metric-value').inner_text()=='—';wrong_hash=False
                wrong_period=True;page.reload();page.wait_for_selector('main[data-status="error"]');wrong_period=False
                current['totales']['registros_validos']+=1;page.reload();page.wait_for_selector('main[data-status="error"]')
                assert not errors,errors
                assert not any('docs.google.com' in u or 'googleapis.com/drive' in u or '_ftr_admin' in u or 'enc.json' in u for u in requested)
                context.close();print(f'Estadísticas {width}px: dos temas, toque/teclado, meses, categorías, muestras, integridad y privacidad OK.')
        finally:browser.close()


if __name__=='__main__':main()
