"""Programación en el panel con GitHub interceptado y cola local temporal."""
import copy
import os
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def check_oneoff_ui(page):
    def api(path):return page.evaluate('''async path=>(await fetch('/api/'+path,{headers:{'X-FTR-CSRF':document.querySelector('meta[name="ftr-csrf"]').content}})).json()''',path)
    remote=api('bootstrap')['remote'];assert remote
    future=datetime.now(ZoneInfo('America/Argentina/Buenos_Aires'))+timedelta(days=1)
    date=future.date().isoformat();clock='18:30';at=date+'T18:30:00-03:00'
    remote=copy.deepcopy(remote);remote.update(oneoffs=dict(version=1,pending={},history=[]),runs=[])
    def route(r):r.fulfill(json=remote)
    page.route('**/api/status',route)
    def refresh():page.locator('#refreshCloud').click();page.wait_for_function('() => document.querySelector("#connectionBadge").textContent==="CONECTADO"')
    def cancel_local(identifier):
        page.locator('[data-order-id="'+identifier+'"] button').click();page.locator('#dialogConfirm').click()
        page.wait_for_function('(id)=>document.querySelector(`[data-order-id="${id}"]`).textContent.includes("Cancelada antes del envío")',arg=identifier)
    def confirm_order():
        previous=[r['id'] for r in api('orders')['orders']]
        page.locator('#dialogConfirm').click()
        page.wait_for_function('''async ids=>{const r=await fetch('/api/orders',{headers:{'X-FTR-CSRF':document.querySelector('meta[name="ftr-csrf"]').content}});return (await r.json()).orders.some(x=>!ids.includes(x.id))}''',arg=previous)
    try:
        page.evaluate("showView('schedules')");refresh()
        initial=[page.locator('#'+k).input_value() for k in ('driveDays','driveTime','cnrtDays','cnrtTime')]
        for key in ('drive','cnrt'):
            page.locator('#'+key+'OneoffDate').fill('2020-01-01');page.locator('#'+key+'OneoffTime').fill('17:30')
            page.locator('[data-oneoff-submit="'+key+'"]').click()
            assert page.locator('#'+key+'OneoffError').inner_text()=='La fecha y hora deben ser posteriores al momento actual.'
            page.locator('#'+key+'OneoffDate').fill(date);page.locator('#'+key+'OneoffTime').fill(clock)
            page.locator('[data-oneoff-submit="'+key+'"]').click();confirm_order()
            page.wait_for_function('() => document.querySelector("#cloudActivity").textContent.includes("Programar actualización única")')
            order=api('orders')['orders'][-1];assert order['status']=='pending' and order['oneoff']['source']==key
            assert page.locator('#'+key+'OneoffStatus').inner_text().startswith('Sin actualización extraordinaria pendiente.')
            cancel_local(order['id'])
        remote['oneoffs']['pending']['cnrt']=dict(id='a'*32,source='cnrt',at=at,status='pending')
        refresh();page.wait_for_selector('[data-oneoff-cancel="cnrt"]')
        assert page.locator('#cnrtOneoffFields').is_hidden()
        page.locator('#cnrtOneoffStatus').get_by_role('button',name='CAMBIAR').click()
        assert page.locator('#cnrtOneoffDate').input_value()==date
        page.locator('#cnrtOneoffTime').fill('19:30');page.locator('[data-oneoff-submit="cnrt"]').click();confirm_order()
        page.wait_for_function('() => document.querySelector("#cnrtOneoffStatus").textContent.includes("Pendiente de envío")')
        order=api('orders')['orders'][-1];assert order['oneoff']['expected_id']=='a'*32 and order['oneoff']['time']=='19:30';cancel_local(order['id'])
        page.locator('[data-oneoff-cancel="cnrt"]').click();confirm_order()
        page.wait_for_function('() => document.querySelector("#cloudActivity").textContent.includes("Cancelar actualización programada")')
        order=api('orders')['orders'][-1];assert order['action']=='oneoff-cancel';cancel_local(order['id'])
        for width in (390,1280):
            page.set_viewport_size(dict(width=width,height=950))
            for theme in ('light','dark'):
                page.evaluate('t=>document.documentElement.dataset.theme=t',theme)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,theme)
                assert page.locator('[data-run="drive"]').is_visible() and page.locator('[data-run="cnrt"]').is_visible()
                assert [page.locator('#'+k).input_value() for k in ('driveDays','driveTime','cnrtDays','cnrtTime')]==initial
                if os.environ.get('FTR_SCREENSHOTS'):
                    folder=Path(os.environ['FTR_SCREENSHOTS']);folder.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(folder/f'programacion-unica-{width}-{theme}.png'),full_page=True)
        print('Programación única UI: dos fuentes, fecha pasada, orden pendiente, cambio, cancelación, calendario intacto, móvil/escritorio y dos temas OK. Sin órdenes reales.')
    finally:page.unroute('**/api/status',route)
