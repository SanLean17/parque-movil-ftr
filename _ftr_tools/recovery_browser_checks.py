"""Estados de agenda en navegador; respuestas de GitHub completamente ficticias."""
import copy
import os
from pathlib import Path


def check_recovery_ui(page):
    remote=page.evaluate('''async()=>{const r=await fetch('/api/bootstrap',{headers:{'X-FTR-CSRF':document.querySelector('meta[name="ftr-csrf"]').content}});return (await r.json()).remote}''')
    remote=copy.deepcopy(remote);remote.update(runs=[],schedule_health=dict(status='disabled'))
    remote['schedule']={key:dict(status='overdue',pending=True,next_due_utc='2026-10-21T20:00:00+00:00') for key in ('drive','cnrt')}
    remote['state']={'drive':{'read_utc':'2026-10-20T20:00:00+00:00'},'publication':{'status':'error'}}
    def route(r):r.fulfill(json=remote)
    page.route('**/api/status',route)
    def refresh(text):
        page.locator('#refreshCloud').click();page.wait_for_function('(text)=>document.querySelector("#driveAgendaNote").textContent.includes(text)',arg=text)
    try:
        page.evaluate("showView('schedules')");refresh('WORKFLOW DESHABILITADO')
        assert page.locator('#driveCloudState').inner_text()=='ACTUALIZACIÓN ATRASADA'
        assert 'PUBLICACIÓN PENDIENTE' in page.locator('#driveAgendaNote').inner_text()
        remote['schedule_health']['status']='unknown';refresh('Estado del workflow sin verificar')
        remote['schedule_health']=dict(status='active',last_scheduled=dict(created_at='2026-10-21T20:37:00Z'))
        remote['state']['publication']['status']='success'
        remote['schedule']['drive'].update(status='saved',pending=False,next_due_utc='2026-10-22T20:00:00+00:00')
        remote['oneoffs']['execution_history']=[dict(source='drive',expected_utc='2026-10-21T20:00:00Z',read_utc='2026-10-21T20:39:00Z',status='success',kind='recovered')]
        refresh('RECUPERADA');note=page.locator('#driveAgendaNote').inner_text()
        assert '17:00' in note and '17:39' in note and 'Próximo horario recurrente' in note
        assert 'PUBLICACIÓN PENDIENTE' not in note
        for width in (390,1280):
            page.set_viewport_size(dict(width=width,height=950))
            for theme in ('light','dark'):
                page.evaluate('t=>document.documentElement.dataset.theme=t',theme)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                if os.environ.get('FTR_SCREENSHOTS'):
                    folder=Path(os.environ['FTR_SCREENSHOTS']);folder.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(folder/f'recuperacion-{width}-{theme}.png'),full_page=True)
        print('Agenda visible: workflow deshabilitado/desconocido/activo, atraso, publicación pendiente y recuperación con hora prevista/real; 2 tamaños y temas OK.')
    finally:page.unroute('**/api/status',route)
