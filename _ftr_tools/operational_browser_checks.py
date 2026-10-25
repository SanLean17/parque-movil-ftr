"""Real controls on a fictitious profile; never dispatches production commands."""
from statistics_browser_checks import api


def check_operational_forms(page):
    original=page.evaluate('JSON.parse(JSON.stringify(state))')
    before={r['id'] for r in api(page,'orders')['value']['orders']}
    try:
        page.evaluate('showView("lines")')
        page.locator('#lineSearch').fill('99998')
        page.locator('#openLineForm').click()
        page.locator('#lineNumber').fill('99998');page.locator('#companyNumber').fill('99999998')
        page.locator('#lineForm button[type=submit]').click()
        row=page.locator('#lineRows tr');assert row.count()==1
        assert '99999998' in row.inner_text()
        row.get_by_role('button',name='Editar',exact=True).click()
        page.locator('#companyNumber').fill('99999997');page.locator('#lineForm button[type=submit]').click()
        assert '99999997' in row.inner_text()
        row.get_by_role('button',name='Desactivar',exact=True).click();page.locator('#dialogConfirm').click()
        assert 'Inactiva' in row.inner_text()
        page.locator('#openLineForm').click();page.locator('#lineNumber').fill('99998');page.locator('#companyNumber').fill('99999997')
        page.locator('#lineForm button[type=submit]').click()
        assert page.locator('#lineError').is_visible() and row.count()==1
        page.locator('#cancelLine').click()
        for year in (2027,2028,2029):
            page.evaluate('showView("source")')
            page.locator('#period').fill(str(year))
            page.locator('#sheetUrl').fill(f'https://docs.google.com/spreadsheets/d/FICTITIOUS_WINDOWS_{year}_SOURCE/edit')
            page.locator('#saveAll').click()
            page.wait_for_function('(year)=>state.period===year',arg=year)
            page.reload();page.wait_for_selector('html[data-ready="true"]')
            page.evaluate('showView("source")')
            assert page.locator('#period').input_value()==str(year)
            assert f'WINDOWS_{year}' in page.locator('#sheetUrl').input_value()
        assert {r['id'] for r in api(page,'orders')['value']['orders']}==before
    finally:
        page.evaluate('(saved)=>{state=saved;dirty=true;populate();}',original)
        page.locator('#saveAll').click();page.evaluate('showView("lines")');page.locator('#lineSearch').fill('')
    print('Windows forms: add line, edit company, disable, duplicate rejection and 2027–2029 draft persistence; no remote dispatch.')
