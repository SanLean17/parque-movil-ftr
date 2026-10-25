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
    published=os.environ.get('FTR_PUBLIC_KIT_URL')
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
            if published:page.on('request',lambda r:requests.append(r.url))
            else:context.route('**/*',route)
            def ready():page.wait_for_selector('main[data-status="ready"]')
            def load():
                page.goto(published or 'https://ftr.test/estadisticas.html');ready()
                page.evaluate('document.fonts.ready')
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
                assert page.locator('#kitTitle + .section-note').inner_text()=='Incidencias independientes de las anomalías mecánicas. Cada fiscalización cuenta una sola vez.'
                assert page.locator('#mechanicsCoverage').count()==0
                assert 'elementos físicos' not in page.locator('section[aria-labelledby=mechanicsTitle]').inner_text().lower()
                if kit['controles_con_incidencia'] and kit['estado']=='disponible':assert page.locator('#kitStatus').is_hidden()
                def check_rows(selected):
                    for row in selected:
                        item=page.locator(f'[data-kit-line="{row["linea"]}"]')
                        value=100*row['incidencias']/row['controles'] if row['controles'] else None
                        assert item.locator('.ratio-value').inner_text()==(f'{value:.1f}'.replace('.',',')+' %' if value is not None else '—')
                        rendered=float(item.locator('.fill').evaluate('e=>e.style.getPropertyValue("--width")').rstrip('%'))
                        assert abs(rendered-(value or 0))<0.00001
                        track=item.locator('.track').bounding_box();fill=item.locator('.fill').bounding_box()
                        assert abs(fill['width']-track['width']*(value or 0)/100)<1
                        assert f'{row["incidencias"]} incidencias KIT / {row["controles"]} controles' in item.locator('.ratio-detail').inner_text()
                check_rows(expected)
                card=page.locator('.kit-highlight').bounding_box();container=page.locator('.kit-highlights').bounding_box()
                if width>=960:
                    assert card['width']<=container['width']/3 and abs(card['x']-container['x'])<1
                    assert abs(card['width']-page.locator('#highlights .highlight').first.bounding_box()['width'])<20
                else:assert abs(card['width']-container['width'])<1
                # The two sections use the same DOM structure and computed styles.
                if expected:
                    for selector,properties in [('.ratio-label',['display','fontSize','fontWeight']),('.ratio-value',['color','fontFamily','fontSize','textAlign']),('.track',['height','backgroundColor','borderRadius']),('.ratio-detail',['fontSize','lineHeight','color'])]:
                        style='(e,ps)=>Object.fromEntries(ps.map(p=>[p,getComputedStyle(e)[p]]))'
                        assert page.locator('#ratios '+selector).first.evaluate(style,properties)==page.locator('#kitLines '+selector).first.evaluate(style,properties)
                for theme in ('light','dark'):
                    page.evaluate('(dark)=>document.documentElement.classList.toggle("dark",dark)',theme=='dark')
                    # Capture the completed theme transition, not its intermediate colors.
                    page.wait_for_timeout(300)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    if output and width in (390,1280):page.locator('section[aria-labelledby=kitTitle]').screenshot(path=str(output/f'kit-{year}-{width}-{theme}.png'))
                    if output and width==1280:
                        page.locator('section[aria-labelledby=mechanicsTitle]').screenshot(path=str(output/f'mecanicas-{year}-{width}-{theme}.png'))
                        page.locator('section[aria-labelledby=proportionTitle]').screenshot(path=str(output/f'fuera-servicio-{year}-{width}-{theme}.png'))
                toggle=page.locator('#showKitLines')
                if len(rows)>5:
                    before=len(requests);toggle.focus();page.keyboard.press('Enter')
                    assert toggle.get_attribute('aria-expanded')=='true'
                    assert toggle.inner_text()=='Mostrar menos'
                    assert page.locator('[data-kit-line]').evaluate_all('ns=>ns.map(n=>Number(n.dataset.kitLine))')==[r['linea'] for r in rows]
                    assert page.locator('[data-kit-line]').count()==len(set(r['linea'] for r in rows))
                    check_rows(rows)
                    page.keyboard.press('Enter');assert toggle.get_attribute('aria-expanded')=='false'
                    assert len(requests)==before,'expansion must not fetch or recalculate'
                    assert page.locator('[data-kit-line]').count()==len(expected)
                    assert toggle.inner_text()==f'Ver todas las líneas ({len(rows)})'
                    toggle.click()
                page.locator('#periodSelect').select_option(str(2025 if year==2026 else 2026));ready()
                assert page.locator('#showKitLines').get_attribute('aria-expanded')=='false'
            # More than five positive lines; ties and zero rows stay deterministic.
            if published:
                assert not errors,errors
                context.close();continue
            six=copy.deepcopy(original[2026]);eligible=[r for r in six['kit_sube']['lineas'] if r['controles']>=2][:6]
            for r in six['kit_sube']['lineas']:r['incidencias']=2 if r in eligible else 0
            six['kit_sube']['controles_con_incidencia']=12;current[2026]=six;load()
            assert page.locator('[data-kit-line]').count()==5
            page.locator('#showKitLines').click();assert page.locator('[data-kit-line]').count()==len(six['lineas'])
            # Coverage warnings remain visible while proportions use all valid controls.
            partial=copy.deepcopy(original[2026]);partial['kit_sube']['estado']='parcial'
            partial['kit_sube']['lineas'][0]['con_novedades']-=1
            current[2026]=partial;load();assert 'Cobertura parcial' in page.locator('#kitStatus').inner_text()
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
    print('KIT: shared percentage rows, compact card, clean copy, annual data, expansion, themes and 4 viewports verified.'+(' Published website.' if published else ' Includes synthetic zero / pending / partial / small samples.'))


if __name__=='__main__':main()
