"""Navegador real con CSV ficticios interceptados, sin Google Sheets ni CNRT."""
import os
import re
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as playwright:
        options = dict(headless=True)
        if os.environ.get('FTR_TEST_BROWSER'):
            options['executable_path'] = os.environ['FTR_TEST_BROWSER']
        browser = playwright.chromium.launch(**options)
        try:
            for width in (390, 1280):
                context = browser.new_context(viewport={'width':width,'height':900}, color_scheme='light')
                failures = []
                page = context.new_page()
                page.on('pageerror', lambda error: failures.append(str(error)))
                missing = {'controls':False, 'fleet':False, 'stale':False}
                numbers = json.loads((ROOT/'_ftr_config.json').read_text())['lines']
                fixture = {}
                for line in numbers:
                    number = line['line']
                    fixture[f'parques/linea{number}.csv'] = f'dominio,interno,linea,empresaNro,razonSocial\nAA111AA,1,{number},9999,EMPRESA FICTICIA\nBB222BB,2,{number},9999,EMPRESA FICTICIA\n'
                    fixture[f'controlados/linea{number}.csv'] = f'linea,fecha,dominio,interno\n{number},20/10/2026,AA111AA,1\n{number},20/10/2026,CC333CC,3\n'
                for name in ('ultima_actualizacion_parque.txt','ultima_actualizacion_controlados.txt'):
                    fixture[name] = '2026-10-21T20:01:00+00:00\n'
                manifest = dict(version='TEST_ONLY', lines=[r['line'] for r in numbers],
                                files_sha256={name:hashlib.sha256(data.encode()).hexdigest() for name,data in fixture.items()})
                def route(request):
                    parsed = urlparse(request.request.url)
                    if parsed.hostname != 'ftr.test':
                        request.continue_()
                        return
                    path = parsed.path.lstrip('/')
                    match = re.fullmatch(r'(parques|controlados)/linea(\d+)\.csv', path)
                    if match:
                        folder, number = match.groups()
                        if folder == 'parques':
                            if missing['fleet']:
                                request.fulfill(status=503, body='Parque ficticio no disponible')
                                return
                            text = fixture[path]
                        else:
                            if missing['controls']:
                                request.fulfill(status=503, body='Fuente ficticia no disponible')
                                return
                            text = fixture[path]
                            if missing['stale']:
                                text = text.replace('AA111AA', 'DD444DD')
                        request.fulfill(status=200, content_type='text/csv', body=text)
                    elif path.startswith('ultima_actualizacion'):
                        request.fulfill(status=200, body=fixture[path])
                    elif path == 'ftr_publicacion.json':
                        request.fulfill(status=200, json=manifest)
                    elif path in ('index.html','linea.html','ftr-publica.js','ftr-datos.js','ftr-historial.js','ftr-historial-publico.js'):
                        request.fulfill(path=str(ROOT/path))
                    else:
                        request.fulfill(status=404, body='Fixture no disponible')
                context.route('**/*', route)
                page.goto('https://ftr.test/index.html')
                page.wait_for_function("document.getElementById('controladas-2').textContent === '1'")
                assert page.locator('#total-2').inner_text() == '2'
                assert page.locator('#porcentaje-2').inner_text() == '50%'
                page.wait_for_function("document.getElementById('fechaControlados').textContent.includes('17:01 hs')")
                page.goto('https://ftr.test/linea.html?id=2')
                page.wait_for_function("document.getElementById('countControlados').textContent.trim() === '1'")
                assert page.locator('#countPendientes').inner_text().strip() == '1'
                row = page.locator('#fleetTbody tr[data-status="CONTROLADO"]')
                assert '20/10/2026' in row.inner_text()
                assert 'hs' not in row.inner_text()
                for label in ('Copiar controlados','Copiar pendientes'):
                    assert page.get_by_role('button', name=label).is_enabled()
                page.evaluate("navigator.clipboard ? navigator.clipboard.writeText = async text => { window.copiedFixture = text; } : 0")
                page.on('dialog', lambda dialog: dialog.dismiss())
                page.get_by_role('button', name='Copiar controlados').click()
                assert 'AA111AA' in page.evaluate('window.copiedFixture')
                page.get_by_role('button', name='Copiar pendientes').click()
                assert 'BB222BB' in page.evaluate('window.copiedFixture')
                page.locator('button[onclick="toggleDarkMode()"]').click()
                assert page.locator('html').evaluate("node => node.classList.contains('dark')")
                page.wait_for_function("getComputedStyle(document.body).backgroundColor === 'rgb(17, 24, 39)'")
                destination = os.environ.get('FTR_SCREENSHOTS')
                if destination:
                    Path(destination).mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(Path(destination)/f'ftr-{width}-dark.png'), full_page=True)
                missing['controls'] = True
                page.reload()
                page.get_by_text('Lectura no disponible. Recargá la página para reintentar.').wait_for()
                assert page.locator('#countPendientes').inner_text() == '—'
                assert page.get_by_role('button', name='Copiar pendientes').is_disabled()
                missing.update(controls=False, fleet=True)
                page.reload()
                page.get_by_text('Lectura no disponible. Recargá la página para reintentar.').wait_for()
                assert page.locator('#countTotal').inner_text() == '—'
                assert page.get_by_role('button', name='Copiar controlados').is_disabled()
                missing.update(fleet=False, stale=True)
                page.reload()
                page.get_by_text('Lectura no disponible. Recargá la página para reintentar.').wait_for()
                assert page.locator('#countTotal').inner_text() == '—'
                page.goto('https://ftr.test/index.html')
                page.wait_for_function("document.getElementById('visita-2').textContent === 'Lectura no disponible'")
                assert page.locator('#controladas-2').inner_text() == '—'
                missing['stale'] = False
                page.goto('https://ftr.test/linea.html?id=2')
                page.wait_for_function("document.getElementById('countTotal').textContent.trim() === '2'")
                page.evaluate(r'''() => renderFleet([{dominio:'AA111AA',interno:'<img src=x onerror="window.injected=true">',marca:'<script>window.injected=true<\/script>'}])''')
                assert page.locator('#fleetTbody img, #fleetTbody script').count() == 0
                assert page.evaluate('window.injected === undefined')
                assert not failures, failures
                context.close()
                print(f'Navegador {width}px: comparación, fecha, copias, tema y error de fuente verificados con datos ficticios.')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
    from browser_statistics import main as statistics_smoke
    statistics_smoke()
