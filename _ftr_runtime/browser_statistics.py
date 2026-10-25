"""Navegador V2: datos ficticios, historial, integridad, privacidad y diseño."""
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from _ftr_runtime.test_source_pipeline import SourcePipelineTests
from _ftr_runtime.public_statistics import FILE, INDEX, ASSETS
from _ftr_runtime.statistics_archive import encoded, entry
from _ftr_runtime.mechanical_dictionary import LEGACY_CATEGORIES


def fixture():
    test=SourcePipelineTests();test.setUp()
    try:
        rows=[['FECHA','LINEA','DOMINIO','INTERNO','ESTADO','NOVEDADES']]
        for line,n in ((36,100),(37,20)):
            for i in range(n):
                rows.append([f'{1+i//10:02}/{1+i%10:02}/2026',line,'AA111AA' if line==36 else 'CC333CC',1,
                    'FUERA DE SERVICIO' if i<13 else 'OBSERVADO' if i<19 else '' if i in (20,21) else 'SIN NOVEDAD',
                    ('R1 cortado, A2 flojo, PF trasero derecho y chicharra' if i<22 else 'sin novedad')+(' - KIT NO COINCIDE' if i<3 else '')])
        test.google([test.sheet('LINEA 36/37',rows)])
        current=json.loads((test.root/FILE).read_text())
        test.config['period']=2027;test.config['lines']=[dict(line=99,company=9999,enabled=True)]
        test.clock=datetime(2027,2,9,20,tzinfo=timezone.utc)
        test.google([test.sheet('LINEA 99',[rows[0],['05/02/2027',99,'ZZ999ZZ',1,'OBSERVADO','R5 pinchado y amortiguador de dirección']])])
        following=json.loads((test.root/FILE).read_text())
        legacy=copy.deepcopy(current);legacy.update(version=1,periodo=2025,lectura_planilla_utc='2025-10-21T20:01:00+00:00',corte_fecha='2025-10-21')
        legacy.pop('kit_sube',None)
        for month in legacy['mensual']:month.pop('dias_con_fiscalizaciones')
        legacy['anomalias']['version_reglas']=1
        legacy['anomalias'].pop('elementos_fisicos');legacy['anomalias'].pop('motor_revision')
        legacy['anomalias']['categorias']=[dict(id=k,cantidad=sum(c['cantidad'] for old in current['anomalias']['categorias'] if old['id']==k for c in old['componentes'] if c['id'] in components),
            componentes=[copy.deepcopy(c) for old in current['anomalias']['categorias'] if old['id']==k for c in old['componentes'] if c['id'] in components]) for k,components in LEGACY_CATEGORIES.items()]
        legacy['anomalias']['identificadas']=sum(c['cantidad'] for c in legacy['anomalias']['categorias'] if c['id']!='otras')
        return {2025:legacy,2026:current,2027:following}
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
            for width in (360,390,430,768,1280,1440):
                context=browser.new_context(viewport=dict(width=width,height=900),has_touch=width<800,color_scheme='light')
                page=context.new_page();errors=[];requested=[];current=copy.deepcopy(fake);wrong_hash=False;wrong_period=False
                page.on('pageerror',lambda e:errors.append(str(e)))
                def route(r):
                    u=urlparse(r.request.url);requested.append(r.request.url)
                    if u.hostname!='ftr.test':
                        if u.hostname in ('fonts.googleapis.com','fonts.gstatic.com','cdnjs.cloudflare.com'):r.continue_()
                        else:r.abort()
                        return
                    name=u.path.lstrip('/')
                    payloads={f'estadisticas/{year}.json':encoded(data) for year,data in current.items()}
                    payloads.update({name:b'2026-10-22T20:01:00+00:00\n' for name in ('ultima_actualizacion_parque.txt','ultima_actualizacion_controlados.txt')})
                    items=[entry(current[y],payloads[f'estadisticas/{y}.json']) for y in sorted(current,reverse=True)]
                    if wrong_hash:
                        for item in items:item['sha256']='0'*64
                    if wrong_period:items[-1]['periodo']+=1
                    idx=encoded(dict(version=1,periodos=items))
                    hashes={path:hashlib.sha256(body).hexdigest() for path,body in payloads.items()}
                    if wrong_hash:hashes={path:'0'*64 for path in hashes}
                    hashes[INDEX]=hashlib.sha256(idx).hexdigest()
                    if name=='ftr_publicacion.json':r.fulfill(json=dict(period=max(current),lines=[v['linea'] for v in current[max(current)]['lineas']],files_sha256=hashes))
                    elif name==INDEX:r.fulfill(body=idx,content_type='application/json')
                    elif name in payloads:r.fulfill(body=payloads[name],content_type='application/json')
                    elif name in (*ASSETS,'ftr-datos.js'):r.fulfill(path=str(ROOT/name))
                    else:r.fulfill(status=404,body='Sin fuentes')
                context.route('**/*',route)
                def ready():page.wait_for_selector('main[data-status="ready"]')
                def select(year):
                    page.locator('#periodSelect').select_option(str(year));ready()
                def open_page():
                    page.goto('https://ftr.test/estadisticas.html');ready()
                def layout():
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'desborde {width}'
                    assert page.locator('.metric').count()==6 and page.locator('.month').count()==12 and page.locator('.category').count()==7
                    assert page.locator('a[href*="_ftr"],a[href*="linea.html"]').count()==0
                    boxes=page.locator('.metric').evaluate_all('ns=>ns.map(n=>{let r=n.getBoundingClientRect();return {x:r.x,y:r.y}})')
                    if width<640:assert boxes[0]['y']==boxes[1]['y'] and boxes[2]['y']>boxes[0]['y']
                    assert page.locator('.metric-value').first.evaluate('(n)=>parseFloat(getComputedStyle(n).fontSize)')>=36
                    accents=page.locator('.metric,.highlight').evaluate_all('ns=>ns.map(n=>{const s=getComputedStyle(n),p=getComputedStyle(n,"::before");return {height:parseFloat(s.borderTopWidth)+parseFloat(p.height),border:s.borderTopColor,accent:p.backgroundColor}})')
                    assert all(a['height']==5 and a['border']==a['accent'] for a in accents),accents
                    text=page.locator('body').inner_text()
                    assert 'FUERA DE SERVICIO POR LÍNEA' in text
                    assert 'Resultados históricos por línea.' in text
                    assert 'Ranking principal:' not in text and 'controles sin estado' not in text
                    assert 'lectura automática válida con NOVEDADES' not in text
                    categories=page.locator('#categories').bounding_box();detail=page.locator('#componentPanel').bounding_box()
                    assert detail['y']>=categories['y']+categories['height'], 'el detalle debe estar debajo'
                    values=page.locator('.metric-value').evaluate_all('ns=>ns.map(n=>n.getBoundingClientRect().top)')
                    assert abs(values[0]-values[1])<1,'cifras desalineadas'
                    if width>=960:
                        tracks=page.locator('#ratios .track').evaluate_all('ns=>ns.map(n=>({x:n.getBoundingClientRect().x,w:n.getBoundingClientRect().width}))')
                        assert max(t['x'] for t in tracks)-min(t['x'] for t in tracks)<1
                        assert max(t['w'] for t in tracks)-min(t['w'] for t in tracks)<1
                open_page()
                page.wait_for_function('document.querySelector("#fechaParque").textContent.includes("17:01")')
                assert page.locator('.ftr-statistics-link').get_attribute('aria-current')=='page'
                assert page.locator('.ftr-brand').get_attribute('href')=='index.html'
                assert '2026' in page.locator('#fechaControlados').inner_text()
                assert page.locator('#periodSelect').input_value()=='2027'
                assert page.locator('[data-metric="registros_validos"] .metric-value').inner_text()=='1'
                direction=page.locator('.component').filter(has=page.get_by_role('heading',name='Amortiguador de dirección',exact=True))
                assert direction.locator('.component-count').inner_text()=='1'
                select(2026)
                assert page.locator('[data-metric="registros_validos"] .metric-value').inner_text()=='120'
                assert page.locator('[data-metric="unidades_repetidas"] .metric-value').inner_text()=='2'
                assert page.locator('#kitTotal').inner_text()=='6'
                assert page.locator('#kitLines button').count()==2
                page.locator('#kitLines [data-kit-line="37"]').click()
                assert '15,0 %' in page.locator('#kitDetail').inner_text()
                for theme in ('light','dark'):
                    if (theme=='dark')!=page.evaluate('document.documentElement.classList.contains("dark")'):page.locator('#themeButton').click()
                    layout()
                    colors=page.locator('.metric-value').evaluate_all('ns=>ns.slice(3).map(n=>getComputedStyle(n).color)')
                    highlights=page.locator('#highlights .highlight .count').evaluate_all('ns=>ns.map(n=>getComputedStyle(n).color)')
                    assert highlights==colors
                    page.locator('[data-month="3"]').click()
                    assert 'MARZO — 12 CONTROLES — 10 DÍAS CON FISCALIZACIONES' in page.locator('#monthSelection').inner_text()
                    page.locator('[data-month="12"]').click();assert 'POSTERIOR' in page.locator('#monthSelection').inner_text()
                    for cat,label in (('direccion','Columna de dirección'),('frenos','Pulmón de freno'),('suspension','Amortiguadores'),('transmision','Cardán'),('neumaticos','Neumáticos delanteros'),('electrico','Señal sonora de marcha atrás'),('otras','Menciones pendientes')):
                        page.locator('[data-category="'+cat+'"]').click();assert label in page.locator('#components').inner_text()
                        counts=[int(v) for v in page.locator('.component-count').all_inner_texts() if v!='—']
                        assert counts==sorted(counts,reverse=True),(cat,counts)
                    page.locator('[data-category="frenos"]').focus();page.keyboard.press('Enter')
                    assert page.locator('#componentTitle').inner_text()=='SISTEMA DE FRENOS'
                    component=page.locator('.component').filter(has=page.get_by_role('heading',name='Pulmón de freno',exact=True))
                    assert component.locator('.component-count').inner_text()=='42'
                    assert component.locator('.state-segment').count()==4
                    assert [n for n in component.locator('.state-item strong').all_inner_texts()]==['26','12','2','2']
                    assert component.locator('.state-item.neutral').is_visible()
                    assert page.locator('.empty-component').count()>0
                    if output and width in (390,1440):
                        page.locator('#componentPanel').scroll_into_view_if_needed()
                        page.screenshot(path=str(output/f'prueba-ficticia-componentes-{width}-{theme}.png'),animations='disabled')
                # Año antiguo con catálogo anterior: no completar días ni componentes.
                select(2025);page.locator('[data-month="3"]').click()
                assert page.locator('#kitTotal').inner_text()=='—'
                assert 'no calculado' in page.locator('#kitStatus').inner_text()
                assert page.locator('#kitLines button').count()==0
                assert 'DÍAS: NO DISPONIBLES' in page.locator('#monthSelection').inner_text()
                page.locator('[data-category="neumaticos"]').click()
                assert page.locator('#components .component-count').all_inner_texts()==['—']*5
                assert 'reglas v1' in page.locator('#historicalNote').inner_text()
                select(2027);assert page.locator('[data-metric="registros_validos"] .metric-value').inner_text()=='1'
                page.locator('#showLines').click();assert page.locator('#smallSamples').is_visible()
                assert page.locator('#smallRatios .ratio-row').count()==1
                # Capturas de entrega: solo datos reales, ningún año ficticio.
                current={actual['periodo']:copy.deepcopy(actual)};open_page()
                assert page.locator('#periodSelect option').count()==1
                for theme in ('light','dark'):
                    if (theme=='dark')!=page.evaluate('document.documentElement.classList.contains("dark")'):page.locator('#themeButton').click()
                    layout();page.locator('[data-category="frenos"]').click()
                    if actual['anomalias']['estado']=='pendiente':assert page.locator('#components .component-count').all_inner_texts()==['—']*10
                    if output:
                        page.evaluate('window.scrollTo(0,0)');page.evaluate('document.fonts.ready')
                        page.screenshot(path=str(output/f'estadisticas-v2-{width}-{theme}.png'),full_page=True,animations='disabled')
                        if width in (390,1440):page.screenshot(path=str(output/f'vista-v2-{width}-{theme}.png'),animations='disabled')
                wrong_hash=True;page.reload();page.wait_for_selector('main[data-status="error"]')
                assert page.locator('[data-metric="registros_validos"] .metric-value').inner_text()=='—';wrong_hash=False
                wrong_period=True;page.reload();page.wait_for_selector('main[data-status="error"]');wrong_period=False
                current[actual['periodo']]['totales']['registros_validos']+=1
                page.reload();page.wait_for_selector('main[data-status="error"]')
                assert page.locator('#months .month').count()==0
                assert not errors,errors
                assert not any('docs.google.com' in u or 'googleapis.com/drive' in u or '_ftr_admin' in u or 'enc.json' in u for u in requested)
                context.close()
                print(f'Estadísticas V2 {width}px: temas, alineación, categorías inferiores, segmentos, años, días e integridad OK.')
        finally:browser.close()


if __name__=='__main__':main()
