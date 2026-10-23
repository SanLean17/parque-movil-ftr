"""UI 06.3.7 real y cola real con GitHub ficticio, sin lecturas de producción."""
import copy
import json
import os
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'_ftr_app'))
import requests
import server
import main0631
from _ftr_runtime.config import load,digest
from _ftr_app.local_clock import write_json
from _ftr_app.outbox import Outbox


def main():
    from playwright.sync_api import sync_playwright
    network={'online':False,'config':load(ROOT),'runs':[],'sent':[]}
    with tempfile.TemporaryDirectory(prefix='ftr-ui-') as temporary,ExitStack() as stack:
        data=Path(temporary)
        def snapshot():
            if not network['online']:raise requests.ConnectionError('Ficticio: sin Internet')
            result=dict(config=copy.deepcopy(network['config']),digest=digest(network['config']),state={},revision='a'*40,oneoffs={'version':1,'pending':{},'history':[]})
            write_json(data/'config_remota.json',result);return result
        def dispatch(row):network['sent'].append(copy.deepcopy(row))
        queue=Outbox(lambda:data,snapshot,lambda since:network['runs'],dispatch)
        stack.enter_context(patch.object(server,'DATA',data))
        stack.enter_context(patch.object(server,'RESOURCE',ROOT/'_ftr_app'))
        stack.enter_context(patch.object(server,'_token','FTR_FICTICIO_NO_CREDENCIAL'))
        stack.enter_context(patch.object(server,'api',side_effect=AssertionError('Red real prohibida')))
        stack.enter_context(patch.object(main0631,'snapshot',snapshot))
        stack.enter_context(patch.object(main0631,'outbox',queue))
        stack.enter_context(patch.object(main0631.agenda_bridge,'last_runs',return_value=[]))
        write_json(data/'config_remota.json',dict(config=network['config'],digest=digest(network['config']),state={},oneoffs={'version':1,'pending':{},'history':[]}))
        main0631.install()
        srv,thread=server.local_server()
        try:
            with sync_playwright() as p:
                options={'headless':True}
                if os.environ.get('FTR_TEST_BROWSER'):options['executable_path']=os.environ['FTR_TEST_BROWSER']
                browser=p.chromium.launch(**options)
                failures=[];external=[]
                def opened(width=1280):
                    context=browser.new_context(viewport={'width':width,'height':950})
                    page=context.new_page();page.on('pageerror',lambda error:failures.append(str(error)))
                    page.on('request',lambda request:external.append(request.url) if not request.url.startswith(server.ORIGIN) else None)
                    page.goto(server.ORIGIN+'/iniciar/'+server.BOOT)
                    page.wait_for_selector('html[data-ready="true"]')
                    return context,page
                def view(page,name):page.evaluate('(name)=>showView(name)',name)
                def confirm(page,selector):
                    page.locator(selector).click();page.locator('#dialogConfirm').click()
                    page.wait_for_function('() => !document.querySelector("#confirmDialog").open')
                context,page=opened()
                from history_browser_checks import check_admin_history
                check_admin_history(page)
                page.locator('#driveTime').fill('18:15');page.locator('#saveAll').click()
                page.wait_for_function('() => document.querySelector("#savedState").textContent.includes("guardado")')
                assert not queue.status()['orders'] and not network['sent']
                page.locator('#themeToggle').click()
                page.wait_for_timeout(150)
                confirm(page,'[data-run="drive"]')
                page.wait_for_selector('[data-order-id]')
                assert queue.status()['orders'][0]['status']=='pending'
                assert 'Pendiente de envío' in page.locator('#cloudActivity').inner_text()
                confirm(page,'[data-run="drive"]');page.wait_for_timeout(150)
                assert len(queue.status()['orders'])==1
                confirm(page,'[data-order-id] button');page.wait_for_timeout(150)
                assert queue.status()['orders'][0]['status']=='cancelled'
                context.close()
                # Un contexto y puerto distintos usan los mismos archivos; no localStorage.
                srv.shutdown();srv.server_close();thread.join(timeout=3)
                srv,thread=server.local_server()
                context,page=opened()
                assert page.locator('#driveTime').input_value()=='18:15'
                assert page.locator('html').get_attribute('data-theme')=='dark'
                confirm(page,'#schedulesForm button[type="submit"]');page.wait_for_timeout(150)
                parent=queue.status()['orders'][-1]
                confirm(page,'[data-run="all"]');page.wait_for_timeout(150)
                child=queue.status()['orders'][-1]
                assert child['depends_on']==parent['id']
                queue.tick();assert not network['sent']
                network['online']=True;queue.tick()
                assert [r['action'] for r in network['sent']]==['config']
                network['config']=copy.deepcopy(network['sent'][0]['config'])
                network['runs']=[dict(id=1,request_id=parent['id'],status='completed',conclusion='success',effect='configuration')]
                queue.tick();assert [r['action'] for r in network['sent']]==['config','all']
                network['runs'].append(dict(id=2,request_id=child['id'],status='completed',conclusion='success',effect='updated'))
                queue.tick();queue.tick();assert len(network['sent'])==2
                page.locator('#refreshCloud').click();page.wait_for_timeout(300)
                assert 'Resultado confirmado en GitHub' in page.locator('#cloudActivity').inner_text()
                confirm(page,'[data-run="cnrt"]');page.wait_for_timeout(150)
                queue.tick();assert queue.status()['orders'][-1]['status']=='conflict'
                page.locator('#refreshCloud').click();page.wait_for_timeout(250)
                assert 'revisar conflicto' in page.locator('#cloudActivity').inner_text()
                # Descartar offline nunca pierde el borrador guardado.
                saved=(data/'borrador.json').read_bytes();network['online']=False
                view(page,'connections');confirm(page,'#resetDemo');page.wait_for_timeout(250)
                assert (data/'borrador.json').read_bytes()==saved
                from oneoff_browser_checks import check_oneoff_ui
                check_oneoff_ui(page)
                from recovery_browser_checks import check_recovery_ui
                check_recovery_ui(page)
                from statistics_browser_checks import check_statistics_admin,check_mechanical_review
                check_statistics_admin(page)
                check_mechanical_review(page)
                screenshots=os.environ.get('FTR_SCREENSHOTS')
                for width in (390,1280):
                    page.set_viewport_size({'width':width,'height':950})
                    for theme in ('light','dark'):
                        page.evaluate('(theme)=>document.documentElement.dataset.theme=theme',theme)
                        for name in ('schedules','source','lines','publish','connections','incidents','statistics','dictionary','diagnostic'):
                            view(page,name)
                            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,theme,name)
                            if screenshots:
                                folder=Path(screenshots);folder.mkdir(parents=True,exist_ok=True)
                                page.screenshot(path=str(folder/f'cliente-{name}-{width}-{theme}.png'),full_page=True)
                assert not failures,failures
                assert not external,external
                context.close();browser.close()
                print('Panel: 9 pantallas, 2 tamaños generales, diccionario también a 900 px, 2 temas; reglas, fragmentos, vista previa, guardado privado, importación, cola y seguridad OK. Cero red externa y cero errores JS. Sin paquete Windows.')
        finally:
            srv.shutdown();srv.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
