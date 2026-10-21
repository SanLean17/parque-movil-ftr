"""Interfaz real: archivos publicados conservados y casos ficticios, sin bots."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as p:
        options=dict(headless=True)
        if os.environ.get('FTR_TEST_BROWSER'):options['executable_path']=os.environ['FTR_TEST_BROWSER']
        browser=p.chromium.launch(**options)
        try:
            for width in (390,1280):
                context=browser.new_context(viewport=dict(width=width,height=900),color_scheme='light')
                page=context.new_page();errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('dialog',lambda d:d.dismiss())
                files={str(f.relative_to(ROOT)).replace('\\','/'):f.read_bytes() for folder in ('parques','controlados') for f in (ROOT/folder).glob('*.csv')}
                files.update({name:(ROOT/name).read_bytes() for name in ('ultima_actualizacion_parque.txt','ultima_actualizacion_controlados.txt')})
                manifest=dict(version='PRUEBA_SIN_FUENTES',period=2026,lines=[x['line'] for x in json.loads((ROOT/'_ftr_config.json').read_text())['lines'] if x['enabled']])
                def seal():manifest['files_sha256']={k:hashlib.sha256(v).hexdigest() for k,v in files.items()}
                seal()
                def route(r):
                    u=urlparse(r.request.url);name=u.path.lstrip('/')
                    if u.hostname!='ftr.test':r.continue_();return
                    if name=='ftr_publicacion.json':r.fulfill(json=manifest)
                    elif name in files:r.fulfill(body=files[name])
                    elif name in ('linea.html','index.html','ftr-publica.js','ftr-datos.js','ftr-historial.js','ftr-historial-publico.js'):r.fulfill(path=str(ROOT/name))
                    else:r.fulfill(status=404,body='Prueba sin fuente')
                context.route('**/*',route)
                def open_line(total):
                    page.goto('https://ftr.test/linea.html?id=154')
                    page.wait_for_function('(v)=>document.querySelector("#countTotal").textContent.trim()===String(v)',arg=total)
                def view(value):page.locator('button[onclick="setFilter(\''+value+'\')"]').click()
                def counts(expected):
                    assert [page.locator('#count'+key).inner_text().strip() for key in ('Total','Controlados','Pendientes')]==list(map(str,expected))
                fleet=list(csv.DictReader(io.StringIO(files['parques/linea154.csv'].decode('utf-8-sig'))))
                controls=list(csv.DictReader(io.StringIO(files['controlados/linea154.csv'].decode('utf-8-sig'))))
                current={r['dominio'] for r in fleet};controlled={r['dominio'] for r in controls};outside=controlled-current
                open_line(len(current));counts((len(current),len(current&controlled),len(current-controlled)))
                assert page.locator('#fleetTbody').evaluate('n=>n.closest("table").querySelectorAll("thead th").length')==8
                for theme in ('light','dark'):
                    page.evaluate('(t)=>document.documentElement.classList.toggle("dark",t==="dark")',theme)
                    for status in ('ALL','CONTROLADO','PENDIENTE'):
                        view(status)
                        if status=='CONTROLADO' and outside:
                            page.wait_for_selector('#historySection:not([hidden])')
                            assert set(page.locator('#historyTbody tr[data-domain]').evaluate_all('rs=>rs.map(r=>r.dataset.domain)'))==outside
                            assert page.locator('#historyTbody').evaluate('n=>n.closest("table").querySelectorAll("thead th").length')==5
                        else:assert page.locator('#historySection').is_hidden()
                        if os.environ.get('FTR_SCREENSHOTS'):
                            folder=Path(os.environ['FTR_SCREENSHOTS']);folder.mkdir(parents=True,exist_ok=True)
                            page.screenshot(path=str(folder/f'154-{width}-{theme}-{status}.png'),full_page=True)
                    view('CONTROLADO')
                    if 'NWS705' in outside:
                        page.locator('tr[data-domain="NWS705"] button').click()
                        detail=page.locator('#history-154-NWS705');assert detail.is_visible()
                        assert detail.locator('p').count()==3
                        assert 'DOMINIO FISCALIZADO' not in detail.inner_text()
                        assert 'HISTORIAL DE CONTROLES' not in detail.inner_text()
                        assert 'PROCEDENCIA' not in detail.inner_text()
                        assert '20/01/2026' not in detail.inner_text()
                        for r in fleet:
                            if r['interno']=='95':assert r['dominio'] in detail.inner_text()
                        assert 'No se encuentra confirmada' in detail.inner_text()
                        if os.environ.get('FTR_SCREENSHOTS'):page.screenshot(path=str(folder/f'154-{width}-{theme}-detalle.png'),full_page=True)
                        page.locator('tr[data-domain="NWS705"] button').click();assert detail.is_hidden()
                        page.locator('#searchInput').fill('95');page.locator('#searchInput').press('End');assert page.locator('#historyTbody tr[data-domain]').count()==1
                        page.locator('#searchInput').fill('SIN_COINCIDENCIA');page.locator('#searchInput').press('End');assert 'No hay coincidencias' in page.locator('#historyTbody').inner_text()
                        page.locator('#searchInput').fill('');page.locator('#searchInput').press('End')
                print(f'Línea 154 conservada {width}px: parque={len(current)}, controlados={len(current&controlled)}, pendientes={len(current-controlled)}, fuera={len(outside)}.')
                # Mezcla, repetidos, mismo interno, contenido inocuo, vuelta y vacío válido.
                files['parques/linea154.csv']=b'dominio,interno,linea\nAA111AA,1,154\nBB222BB,2,154\n'
                files['controlados/linea154.csv']=b'linea,fecha,dominio,interno\n154,20/03/2026,AA111AA,1\n154,12/05/2026,CC333CC,2\n'
                side=dict(version=1,linea=154,periodo=2026,controles_sha256=hashlib.sha256(files['controlados/linea154.csv']).hexdigest(),
                          controles=[dict(dominio=d,interno=i,fecha=f) for d,i,f in [('AA111AA','1','2026-03-20'),('CC333CC','2','2026-01-20'),('CC333CC','2','2026-05-12')]])
                files['historial/linea154.json']=json.dumps(side).encode();seal();open_line(2);counts((2,1,1));view('CONTROLADO')
                page.wait_for_selector('tr[data-domain="CC333CC"]');page.locator('tr[data-domain="CC333CC"] button').click()
                detail=page.locator('#history-154-CC333CC');assert detail.locator('li').count()==0 and detail.locator('p').count()==3
                assert 'BB222BB' in detail.inner_text()
                page.evaluate('navigator.clipboard.writeText=async t=>{window.copied=t}')
                page.get_by_role('button',name='Copiar controlados').click()
                assert 'AA111AA' in page.evaluate('window.copied') and 'CC333CC' not in page.evaluate('window.copied')
                page.get_by_role('button',name='Copiar pendientes').click()
                assert 'BB222BB' in page.evaluate('window.copied') and 'CC333CC' not in page.evaluate('window.copied')
                side['controles_sha256']='0'*64;files['historial/linea154.json']=json.dumps(side).encode();seal();open_line(2);view('CONTROLADO')
                page.wait_for_selector('tr[data-domain="CC333CC"]');assert 'No se pudo verificar' in page.locator('#historyNote').inner_text()
                files['parques/linea154.csv']+=b'CC333CC,2,154\n';seal();open_line(3);view('CONTROLADO');counts((3,2,1));assert page.locator('#historySection').is_hidden()
                files['parques/linea154.csv']=b'dominio,interno,linea\n';seal();open_line(0);view('CONTROLADO');counts((0,0,0))
                page.wait_for_selector('tr[data-domain="CC333CC"]');assert page.locator('#historyTbody tr[data-domain]').count()==2
                files['controlados/linea154.csv']=b'linea,fecha,dominio,interno\n154,,CC333CC,\n';files.pop('historial/linea154.json');seal();open_line(0);view('CONTROLADO')
                page.wait_for_selector('tr[data-domain="CC333CC"]');page.locator('tr[data-domain="CC333CC"] button').click()
                assert 'REFERENCIA ACTUAL DEL INTERNO: No disponible.' in page.locator('#history-154-CC333CC').inner_text()
                assert 'Información no disponible' in page.locator('tr[data-domain="CC333CC"]').inner_text()
                assert not errors,errors
                context.close()
        finally:browser.close()
    print('Historial público: temas, tamaños, buscador, copias, mezcla, repetidos, reaparición, vacío, faltantes y versión inconsistente OK. Sin fuentes.')


if __name__=='__main__':main()
