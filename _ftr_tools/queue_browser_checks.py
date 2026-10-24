"""Recovery UI on source and real EXE, synthetic disk profile and GET evidence."""
import copy,json,os
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import Mock
from _ftr_app.outbox import Outbox
from _ftr_app.queue_runs import RunScan
from _ftr_runtime.config import load,digest
from _ftr_runtime import dictionary_rules as rules

def check_queue_recovery(page,profile):
    profile=Path(profile);file=profile/'ordenes.json';original=file.read_bytes() if file.exists() else None
    now=datetime.now(timezone.utc);clock=[now-timedelta(minutes=10)]
    cfg=load(Path(__file__).resolve().parents[1]);remote=dict(config=cfg,digest=digest(cfg),dictionary_digest=rules.digest(rules.EMPTY))
    runs=Mock(return_value=[]);dispatch=Mock(side_effect=TimeoutError('Ficticio: respuesta perdida'))
    queue=Outbox(lambda:profile,lambda:remote,runs,dispatch,lambda:clock[0])
    queue.save(dict(version=1,orders=[]))
    command=dict(expected_dictionary=rules.digest(rules.EMPTY),reglas=[dict(expresion='X12',categoria='direccion',componente='barra_larga',habilitada=True)])
    first=queue.enqueue(dict(action='dictionary-save',statistical=command),remote);queue.tick()
    command=copy.deepcopy(command);command['reglas'][0]['expresion']='X13'
    second=queue.enqueue(dict(action='dictionary-save',statistical=command),remote)
    third=queue.enqueue(dict(action='drive'),remote);clock[0]=now
    def refresh():
        page.evaluate("showView('schedules')");page.locator('#refreshCloud').click()
        page.wait_for_function('(id)=>!!document.querySelector(`[data-order-id="${id}"]`)',arg=first['id'])
    def intercept(route):
        payload=route.request.post_data_json
        try:
            path=route.request.url.rsplit('/',1)[-1]
            response=queue.check(payload['request_id']) if path=='check' else queue.resolve(payload['request_id'],payload.get('confirmation')) if path=='resolve' else queue.resume(payload.get('confirmation'))
            route.fulfill(status=200,json=response)
        except ValueError as error:route.fulfill(status=400,json={'error':str(error)})
    try:
        refresh();page.wait_for_selector('#queueReview:not([hidden])')
        assert page.locator('#queueResolve').is_disabled()
        # The actual server/EXE has no remote access in the test: an incomplete
        # lookup cannot enable resolution. This request is NOT intercepted.
        page.locator('#queueCheck').click()
        page.wait_for_function('()=>!document.querySelector("#queueCheck").disabled')
        assert page.locator('#queueResolve').is_disabled()
        assert queue.read()['orders'][0]['status']=='unknown'
        runs.return_value=RunScan([],dict(complete=True,examined=351,requests=4))
        for path in ('check','resolve','resume'):page.route('**/api/orders/'+path,intercept)
        page.locator('#queueCheck').click();page.wait_for_function('()=>!document.querySelector("#queueResolve").disabled')
        assert 'no demuestra' in page.locator('#queueEvidence').inner_text()
        page.locator('#queueBlocked').click();assert page.locator('[data-order-id="'+first['id']+'"]').evaluate('n=>n===document.activeElement')
        assert page.locator('#cloudActivity .badge.good').count()==0
        for width in (390,900,1280):
            page.set_viewport_size(dict(width=width,height=950))
            for theme in ('light','dark'):
                page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,theme)
                page.locator('#queueCheck').hover();page.locator('#queuePending').click()
                page.locator('#queueReview').scroll_into_view_if_needed()
                output=os.environ.get('FTR_QUEUE_SCREENSHOTS')
                if output:
                    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
                    page.locator('#queueReview').screenshot(path=str(folder/f'cola-{width}-{theme}.png'))
        page.locator('#queueResolve').click();assert 'PAUSADAS' in page.locator('#confirmDialog').inner_text()
        page.locator('#dialogConfirm').click();page.wait_for_selector('#queueResume:not([hidden])')
        saved=queue.read();assert saved['paused'] and saved['orders'][0]['status']=='resolved'
        assert [r['id'] for r in saved['orders']]==[first['id'],second['id'],third['id']]
        assert [r['status'] for r in saved['orders'][1:]]==['pending','pending']
        assert len(saved['orders'][0]['checks'])>=2
        dispatch.assert_called_once()
        page.locator('#queuePending').click();assert 'Cerrada sin confirmar' in page.locator('#cloudActivity').inner_text()
        page.locator('#queueResume').click();page.locator('#dialogConfirm').click()
        page.wait_for_function('()=>document.querySelector("#queueReview").hidden')
        assert not queue.read()['paused'];dispatch.assert_called_once()  # no background sender in tests
        print('Cola UI: tres órdenes ficticias, comprobación incompleta bloqueada, evidencia completa, resolución confirmada, pausa y continuación; 3 tamaños y 2 temas OK. Sin órdenes reales.')
    finally:
        for path in ('check','resolve','resume'):page.unroute('**/api/orders/'+path,intercept)
        if original is None:file.unlink(missing_ok=True)
        else:file.write_bytes(original)
        page.locator('#refreshCloud').click()
