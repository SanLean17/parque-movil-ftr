"""Mismo contrato de estadísticas en el servidor fuente y el ejecutable real."""
import os
from pathlib import Path


def check_admin_history(page):
    report=dict(periodo=2026,revision_repositorio='FICTICIO',inicio_lectura_utc='2026-10-21T20:00:00Z',
                fecha_parque_comparado_utc='2026-10-20T01:00:00Z',estadisticas=[dict(linea=154,
                parque_publicado=2,coinciden_parque=1,pendientes_actuales=1,cobertura_actual_pct=50,no_en_parque=2)])
    issues=[dict(codigo='NO_EN_PARQUE',linea=154,dominio_ingresado=domain,interno=internal,fecha_control=date,
                 candidatos_mismo_interno=[dict(dominio=current,interno=internal)])
            for domain,internal,date,current in [('CC333CC','1','2026-01-20','AA111AA'),
                ('CC333CC','1','2026-03-20','AA111AA'),('DD444DD','2','2026-05-12','BB222BB')]]
    detail=dict(version=3,periodo=2026,revision_repositorio='FICTICIO',detectado_utc=report['inicio_lectura_utc'],incidencias=issues,repetidos=[])
    original=page.evaluate('''() => ({report:diagnosticReport,details:adminDetails,theme:document.documentElement.dataset.theme})''')
    viewport=page.viewport_size
    page.evaluate('''v=>{diagnosticReport={...diagnosticReport,...v.report};adminDetails=v.detail;statisticsMode='cobertura';renderStatistics();showView('statistics')}''',dict(report=report,detail=detail))
    try:
        for width in (390,1280):
            page.set_viewport_size(dict(width=width,height=950))
            for theme in ('light','dark'):
                page.evaluate('t=>document.documentElement.dataset.theme=t',theme)
                page.locator('#statisticsSearch').fill('999')
                assert page.locator('[data-history-line]').count()==0
                page.locator('#statisticsSearch').fill('154')
                assert page.locator('#statisticsHeads th').count()==6
                button=page.locator('[data-history-line="154"]');button.click()
                expanded=page.locator('#statistics-history-154')
                assert expanded.is_visible()
                assert expanded.locator('[data-history-domain]').count()==2
                record=expanded.locator('[data-history-domain="CC333CC"]')
                record.locator('summary').click()
                text=record.inner_text()
                for expected in ('AA111AA','20/01/2026','20/03/2026','Información no disponible','No se encuentra confirmada'):
                    assert expected in text,expected
                assert page.locator('#statisticsRows [data-key="cobertura_actual_pct"]').inner_text()=='50%'
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,theme)
                if os.environ.get('FTR_SCREENSHOTS'):
                    folder=Path(os.environ['FTR_SCREENSHOTS']);folder.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(folder/f'historial-admin-{width}-{theme}.png'),full_page=True)
                button.click();assert expanded.is_hidden()
        page.locator('[data-statistics-mode="resultados"]').click();assert page.locator('[data-history-line]').count()==0
        page.locator('[data-statistics-mode="cobertura"]').click()
        page.evaluate('() => {adminDetails=null;renderStatistics()}')
        page.locator('[data-history-line="154"]').click()
        assert 'Información no disponible' in page.locator('#statistics-history-154').inner_text()
        print('Historial administrativo: filtro, indicador intacto, repetidos, referencias, detalle ausente, dos temas y dos tamaños OK.')
    finally:
        page.evaluate('''v=>{diagnosticReport=v.report;adminDetails=v.details;document.documentElement.dataset.theme=v.theme;document.querySelector('#statisticsSearch').value='';renderStatistics();showView('schedules')}''',original)
        page.set_viewport_size(viewport)
