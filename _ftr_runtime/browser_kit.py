"""KIT visual acceptance against repository aggregates and synthetic variations."""
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
from _ftr_runtime.statistics_archive import encoded,entry
from _ftr_runtime.public_statistics import ASSETS


def main():
    original={year:json.loads((ROOT/f'estadisticas/{year}.json').read_bytes()) for year in (2025,2026)}
    output=Path(os.environ['FTR_KIT_SCREENSHOTS']) if os.environ.get('FTR_KIT_SCREENSHOTS') else None
    if output:output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        options={'headless':True}
        if os.environ.get('FTR_TEST_BROWSER'):options['executable_path']=os.environ['FTR_TEST_BROWSER']
        browser=p.chromium.launch(**options)
        for width in (360,390,740,1280):
            context=browser.new_context(viewport={'width':width,'height':950});page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            current=copy.deepcopy(original);requests=[]
            def route(r):
                name=urlparse(r.request.url).path.lstrip('/');requests.append(name)
                payloads={f'estadisticas/{year}.json':encoded(data) for year,data in current.items()}
                index=encoded(dict(version=1,periodos=[entry(data,payloads[f'estadisticas/{year}.json']) for year,data in sorted(current.items(),reverse=True)]))
                hashes={name:hashlib.sha256(body).hexdigest() for name,body in payloads.items()};hashes['estadisticas/indice.json']=hashlib.sha256(index).hexdigest()
                if name=='ftr_publicacion.json':r.fulfill(json=dict(period=2026,lines=[v['linea'] for v in current[2026]['lineas']],files_sha256=hashes))
                elif name=='estadisticas/indice.json':r.fulfill(body=index,content_type='application/json')
                elif name in payloads:r.fulfill(body=payloads[name],content_type='application/json')
                elif name in (*ASSETS,'ftr-datos.js','timestamp.json'):r.fulfill(path=str(ROOT/name))
                else:r.fulfill(status=404,body='No external sources in this test')
            context.route('**/*',route)
            def ready():page.wait_for_selector('main[data-status="ready"]')
            def load():page.goto('https://ftr.test/estadisticas.html');ready()
            load()
            for year in (2026,2025):
                page.locator('#periodSelect').select_option(str(year));ready()
                data=current[year];kit=data['kit_sube'];rows=sorted(kit['lineas'],key=lambda r:(-r['incidencias'],r['linea']))
                expected=rows if len(rows)<=5 else [r for r in rows if r['incidencias']>0][:5]
                assert page.locator('#kitTotal').inner_text()==str(kit['controles_con_incidencia'])
                assert page.locator('[data-kit-line]').evaluate_all('ns=>ns.map(n=>Number(n.dataset.kitLine))')==[r['linea'] for r in expected]
                assert page.locator('#highlights .highlight').count()==3
                assert page.locator('#highlights .red .count').inner_text()==str(data['destacados']['fuera_de_servicio']['cantidad'])
                assert page.locator('.kit-highlight h3').inner_text()=='CONTROLES CON INCIDENCIA DE KIT SUBE'
                for theme in ('light','dark'):
                    page.evaluate('(dark)=>document.documentElement.classList.toggle("dark",dark)',theme=='dark')
                    # Capture the completed theme transition, not its intermediate colors.
                    page.wait_for_timeout(300)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    if output and width in (390,1280):page.locator('section[aria-labelledby=kitTitle]').screenshot(path=str(output/f'kit-{year}-{width}-{theme}.png'))
                toggle=page.locator('#showKitLines')
                if len(rows)>5:
                    before=len(requests);toggle.focus();page.keyboard.press('Enter')
                    assert toggle.get_attribute('aria-expanded')=='true'
                    assert toggle.inner_text()=='VER MENOS'
                    assert page.locator('[data-kit-line]').evaluate_all('ns=>ns.map(n=>Number(n.dataset.kitLine))')==[r['linea'] for r in rows]
                    assert page.locator('[data-kit-line]').count()==len(set(r['linea'] for r in rows))
                    page.keyboard.press('Enter');assert toggle.get_attribute('aria-expanded')=='false'
                    assert len(requests)==before,'expansion must not fetch or recalculate'
                    assert page.locator('[data-kit-line]').count()==len(expected)
                    toggle.click()
                page.locator('#periodSelect').select_option(str(2025 if year==2026 else 2026));ready()
                assert page.locator('#showKitLines').get_attribute('aria-expanded')=='false'
            # More than five positive lines; ties and zero rows stay deterministic.
            six=copy.deepcopy(original[2026]);eligible=[r for r in six['kit_sube']['lineas'] if r['controles']>=2][:6]
            for r in six['kit_sube']['lineas']:r['incidencias']=2 if r in eligible else 0
            six['kit_sube']['controles_con_incidencia']=12;current[2026]=six;load()
            assert page.locator('[data-kit-line]').count()==5
            page.locator('#showKitLines').click();assert page.locator('[data-kit-line]').count()==len(six['lineas'])
            # Unknown coverage is never presented as a confirmed zero.
            pending=copy.deepcopy(original[2026]);pending['kit_sube'].update(estado='pendiente',controles_con_incidencia=None)
            for row in pending['kit_sube']['lineas']:row.update(incidencias=None,con_novedades=None)
            current[2026]=pending;load();assert page.locator('#kitTotal').inner_text()=='—'
            assert page.locator('#showKitLines').is_hidden() and page.locator('[data-kit-line]').count()==0
            # Small valid period: use the existing source fixture, not malformed totals.
            from _ftr_runtime.browser_statistics import fixture
            current[2026]=fixture()[2026];load()
            assert page.locator('#showKitLines').is_hidden() and page.locator('[data-kit-line]').count()==2
            assert not errors,errors
            context.close()
        browser.close()
    print('KIT: card, real annual aggregates, <=5 / >5, expansion, zero, pending, themes and 4 viewports verified.')


if __name__=='__main__':main()
