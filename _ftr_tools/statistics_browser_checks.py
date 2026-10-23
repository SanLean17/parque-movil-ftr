"""Flujos del diccionario con API real e informes ficticios, sin red externa."""
import copy
import json
import os
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from _ftr_runtime import dictionary_rules as rules
from _ftr_runtime.config import load,digest


def api(page,path,body=None):
    return page.evaluate('''async ({path,body})=>{const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-FTR-CSRF':document.querySelector('meta[name="ftr-csrf"]').content},body:body?JSON.stringify(body):undefined});return {status:r.status,value:await r.json()}}''',dict(path=path,body=body))


def check_statistics_admin(page):
    # La navegación y el importador no dependen de valores de año hardcodeados.
    page.evaluate('showView("source")')
    assert page.locator('[data-page=source] #technicalDictionary').count()==0
    page.locator('#historicalImporter summary').first.click()
    assert page.locator('#historicalPeriod').input_value()==''
    assert 'IMPORTAR OTRO AÑO' in page.locator('#historicalImporter').inner_text()
    assert 'Utilizá esta opción' in page.locator('#historicalImporter').inner_text()
    page.locator('.nav [data-view=dictionary]').click()
    assert page.locator('#technicalDictionary').is_visible()
    assert page.locator('#confirmedRules').is_visible()


def check_mechanical_review(page, binary_profile=None):
    import server
    from _ftr_runtime.test_mechanical_review import ReviewTests
    test=ReviewTests();test.setUp()
    try:
        sheets=test.source();sheet=sheets[0]
        for row,text in enumerate(['TENSOR PUNTA','TENSOR PUNTA','BARRA CORTA TRAS, PF3, TENSOR SUPERIOR DERECHO, A2 SUELTO'],6):
            for col,value in enumerate(['05/02/2025','DD444DD',12,'OBSERVADO',text],1):sheet.cells[row,col]=value
        test.source=lambda:sheets
        public,report,detail=test.build();private=detail['novedades_sin_clasificar']
        cfg=load(Path(__file__).resolve().parents[1]);current=copy.deepcopy(public);current['periodo']=2026
        remote=dict(dictionary=copy.deepcopy(rules.EMPTY),expected_dictionary=rules.digest(rules.EMPTY),expected=digest(cfg),period=2026,periods=[2026,2025],statistics={'2025':public,'2026':current},hashes={},publication={'2025':True,'2026':True})
        cipher=Fernet(Fernet.generate_key())
        with ExitStack() as stack:
            if binary_profile:
                stack.enter_context(patch.object(server,'DATA',binary_profile))
                (server.DATA/'informe.dpapi').write_bytes(server.protect(json.dumps({'report':report,'details':detail}).encode()))
            else:
                stack.enter_context(patch.object(server,'diagnostic_cache',return_value={'report':report,'details':detail}))
                stack.enter_context(patch.object(server,'protect',side_effect=lambda data,decrypt=False:cipher.decrypt(data) if decrypt else cipher.encrypt(data)))
            path=server.DATA/'diccionario_remoto.json';old=path.read_bytes() if path.exists() else None
            server.write_json(path,remote)
            def remote_status(route):
                csrf=page.locator('meta[name="ftr-csrf"]').get_attribute('content')
                result=page.request.get(page.url.split('/')[0]+'//'+page.url.split('/')[2]+'/api/statistics-admin',headers={'X-FTR-CSRF':csrf})
                route.fulfill(response=result)
            page.route('**/api/statistics-admin?remote=1',remote_status)
            page.evaluate('showView("dictionary")');page.locator('#technicalRefresh').click()
            page.wait_for_function('()=>document.querySelector("#dictionaryPeriod").options.length===2')
            page.locator('#dictionaryPeriod').select_option('2025')
            assert '2025 — IMPORTADO' in page.locator('#historicalPeriods').text_content()
            assert '2026 — PERÍODO ACTIVO' in page.locator('#historicalPeriods').text_content()
            # Confirmación general, revisión de apariciones y cancelación sin escrituras.
            page.locator('#mechanicalSearch').fill('JGO B LARGA');page.locator('#mechanicalState').select_option('observado')
            item=page.locator('#mechanicalExpressions>details').first;item.locator('summary').click()
            item.get_by_role('button',name='Ver registros originales',exact=True).click()
            cards=item.locator('article');assert cards.count()==2
            assert cards.first.locator('.dictionary-original').inner_text()=='JGO B LARGA; barra larga; JGO B LARGA'
            assert cards.first.locator('mark').count()==2
            assert 'AA111AA' in cards.first.inner_text() and '2025-02-01' in cards.first.inner_text()
            def classify(card=cards.first):
                card.get_by_role('button',name='CLASIFICAR EXPRESIÓN',exact=True).click()
                page.wait_for_selector('#dictionaryMeaning')
                assert card.locator('.dictionary-editor').count()==1
                page.locator('#dictionaryMeaning').select_option('component')
                form=card.locator('.dictionary-editor');form.get_by_label('Componente',exact=True).select_option('barra_larga');return form
            form=classify();form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True).click()
            page.wait_for_selector('.dictionary-preview:not([hidden])')
            assert '2 registros potencialmente afectados' in form.inner_text()
            assert 'Otras / sin clasificar: 6 → 4' in form.inner_text()
            form.locator('.dictionary-preview summary').first.click();form.locator('.dictionary-preview').get_by_role('button',name='Ver registros',exact=True).first.click()
            assert 'AA111AA' in form.locator('.dictionary-preview').inner_text()
            before=len(api(page,'orders')['value']['orders']);form.locator('.dictionary-preview').get_by_role('button',name='CANCELAR',exact=True).click()
            assert len(api(page,'orders')['value']['orders'])==before
            form=classify();form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True).click();page.wait_for_selector('.dictionary-preview:not([hidden])')
            form.get_by_label('Expresión técnica',exact=True).fill('JGO B LARGA ')
            assert form.locator('.dictionary-preview').is_hidden()
            form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True).click();page.wait_for_selector('.dictionary-preview:not([hidden])')
            form.get_by_role('button',name='GUARDAR REGLA GENERAL',exact=True).click();page.locator('#dialogConfirm').click()
            page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("Orden guardada")')
            row=api(page,'orders')['value']['orders'][-1];assert row['action']=='dictionary-save'
            for forbidden in ('AA111AA','novedades_original','referencias'):assert forbidden not in json.dumps(row['statistical'])
            assert api(page,'orders/cancel',{'request_id':row['id']})['status']==200
            # Simular la regla confirmada remotamente; editar/deshabilitar no la borra.
            remote['dictionary']=rules.proposed(rules.EMPTY,row['statistical']['reglas'],rules.digest(rules.EMPTY))
            remote['expected_dictionary']=rules.digest(remote['dictionary']);server.write_json(path,remote)
            page.locator('#technicalRefresh').click()
            page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("revisión 2.")')
            page.locator('#confirmedRules summary').click();page.locator('#technicalRules').get_by_role('button',name='Modificar',exact=True).click()
            edit=page.locator('.dictionary-editor');edit.get_by_label('Habilitada para futuras lecturas').uncheck()
            edit.get_by_role('button',name='VER IMPACTO DEL CAMBIO',exact=True).click();page.wait_for_selector('.dictionary-preview:not([hidden])')
            edit.get_by_role('button',name='GUARDAR REGLA GENERAL',exact=True).click();page.locator('#dialogConfirm').click()
            page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("Orden guardada")')
            changed=api(page,'orders')['value']['orders'][-1];assert changed['statistical']['reglas'][0]['habilitada'] is False
            api(page,'orders/cancel',{'request_id':changed['id']})
            remote['dictionary']=copy.deepcopy(rules.EMPTY);remote['expected_dictionary']=rules.digest(rules.EMPTY);server.write_json(path,remote)
            page.locator('#technicalRefresh').click();page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("revisión 1.")')
            # Regla contextual: dos registros, un tensor por registro, sin doble conteo.
            page.locator('#mechanicalSearch').fill('PUNTA')
            item=page.locator('#mechanicalExpressions>details').first;item.locator('summary').click();item.get_by_role('button',name='Ver registros originales',exact=True).click()
            item.locator('article').first.get_by_role('button',name='CLASIFICAR EXPRESIÓN',exact=True).click();page.wait_for_selector('#dictionaryMeaning')
            form=page.locator('.dictionary-editor');assert page.locator('#dictionaryMeaning').input_value()=='descriptor'
            assert form.get_by_label('Categoría',exact=True).count()==0
            form.get_by_label('Significado del descriptor').select_option('extremo')
            form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True).click();page.wait_for_selector('.dictionary-preview:not([hidden])')
            assert '2 registros potencialmente afectados' in form.inner_text()
            # Hover, focus, ubicación inmediata y capturas en ambos temas.
            page.locator('#toast').wait_for(state='hidden')
            output=os.environ.get('FTR_SCREENSHOTS')
            for width in (390,900,1280):
                page.set_viewport_size({'width':width,'height':950})
                for theme in ('light','dark'):
                    page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,theme)
                    target=form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True)
                    target.hover();assert target.evaluate('(b)=>getComputedStyle(b).boxShadow')!='none'
                    target.focus();page.keyboard.press('Tab');page.keyboard.press('Shift+Tab')
                    assert target.evaluate('(b)=>b===document.activeElement&&getComputedStyle(b).outlineStyle!=="none"')
                    if output:
                        folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
                        page.evaluate('()=>{document.activeElement?.blur();window.scrollTo(0,0)}')
                        page.screenshot(path=str(folder/f'diccionario-contexto-{width}-{theme}.png'),full_page=True)
                        form.screenshot(path=str(folder/f'diccionario-editor-{width}-{theme}.png'))
            page.set_viewport_size({'width':1280,'height':950})
            form.locator('.dictionary-preview').get_by_role('button',name='CANCELAR',exact=True).click()
            # Edición de varias anomalías desde el original completo, sin copiarlo.
            page.locator('#dictionaryReview summary').click();page.locator('#dictionaryRecordSearch').fill('BARRA CORTA TRAS')
            page.locator('#dictionaryFind').click();page.wait_for_selector('#dictionaryRecords article')
            card=page.locator('#dictionaryRecords article').first;card.get_by_role('button',name='CLASIFICAR EXPRESIÓN',exact=True).click();page.wait_for_selector('#dictionaryMeaning')
            page.locator('#dictionaryMeaning').select_option('multiple');form=page.locator('.dictionary-editor')
            assert form.get_by_role('button',name='Eliminar interpretación',exact=True).count()==4
            form.get_by_role('button',name='Unir con siguiente',exact=True).first.click()
            assert form.get_by_role('button',name='Eliminar interpretación',exact=True).count()==3
            source=form.locator('textarea');source.evaluate('(t)=>{t.focus();t.setSelectionRange(17,17);t.dispatchEvent(new Event("select"))}')
            form.get_by_role('button',name='Dividir en el cursor',exact=True).first.click()
            assert form.get_by_role('button',name='Eliminar interpretación',exact=True).count()==4
            form.get_by_role('button',name='Eliminar interpretación',exact=True).nth(1).click()
            source.evaluate('(t)=>{t.focus();t.setSelectionRange(17,20);t.dispatchEvent(new Event("select"))}')
            form.get_by_role('button',name='Crear fragmento con la selección',exact=True).click()
            assert form.get_by_role('button',name='Eliminar interpretación',exact=True).count()==4
            form.get_by_label('Resultado de interpretación',exact=True).nth(1).select_option('pendiente')
            form.get_by_role('button',name='VISTA PREVIA SOLO ESTE REGISTRO',exact=True).click();page.wait_for_selector('.dictionary-preview:not([hidden])')
            assert '1 registros potencialmente afectados' in form.inner_text()
            if output:
                for theme in ('light','dark'):
                    page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
                    page.screenshot(path=str(Path(output)/f'diccionario-fragmentos-{theme}.png'),full_page=True)
            form.get_by_role('button',name='GUARDAR SOLO ESTE REGISTRO',exact=True).click();page.locator('#dialogConfirm').click()
            page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("particular guardada")')
            assert len(api(page,'orders')['value']['orders'])==before+2
            assert (server.DATA/'interpretaciones.dpapi').exists()
            assert b'BARRA CORTA TRAS' not in (server.DATA/'interpretaciones.dpapi').read_bytes()
            # Reapertura y rechazo de importación duplicada.
            page.locator('#dictionaryFind').click();page.wait_for_selector('#dictionaryRecords article')
            page.locator('#dictionaryRecords article').first.get_by_role('button',name='CLASIFICAR EXPRESIÓN',exact=True).click();page.wait_for_selector('#dictionaryMeaning')
            assert 'interpretación particular guardada' in page.locator('.dictionary-editor').inner_text()
            page.locator('#dictionaryMeaning').select_option('pending');page.locator('.dictionary-editor').get_by_role('button',name='CANCELAR',exact=True).click()
            page.evaluate('showView("source")');page.locator('#historicalPeriod').fill('2025');page.locator('#historicalUrl').fill('https://docs.google.com/spreadsheets/d/HISTORICAL_FICTITIOUS_1234567/edit')
            page.locator('#historicalForm button').click();assert 'ya está disponible' in page.locator('#historicalStatus').inner_text()
            page.locator('#historicalPeriod').fill('2024');page.locator('#historicalForm button').click();page.locator('#dialogConfirm').click()
            page.wait_for_function('()=>document.querySelector("#historicalStatus").textContent.includes("Importación solicitada")')
            row=api(page,'orders')['value']['orders'][-1];assert row['action']=='history-import' and row['statistical']['period']==2024
            api(page,'orders/cancel',{'request_id':row['id']})
            # Acceso desde Estadísticas conserva el año.
            page.evaluate('showView("statistics")');page.locator('#mechanicalPeriod').select_option('2025');page.locator('#openDictionary').click()
            assert page.locator('#dictionaryPeriod').input_value()=='2025'
            check_general_descriptors(page,server,test,path,remote,report,detail,binary_profile)
            page.unroute('**/api/statistics-admin?remote=1')
            if not binary_profile:
                (server.DATA/'interpretaciones.dpapi').unlink(missing_ok=True)
                if old is None:path.unlink(missing_ok=True)
                else:path.write_bytes(old)
    finally:test.tearDown()


def check_general_descriptors(page,server,test,path,remote,report,detail,binary_profile):
    from _ftr_runtime.test_general_descriptors import CASES
    texts=[*CASES,'EXTREMO','BARRA LARGA EXTREMO BARRA CORTA','EXTREMO BARRA LARGA; EXTREMOS']
    sheets=[test.sheet('Línea 999',[['FECHA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],
        *[['01/02/2025','AA111AA',7,'OBSERVADO',text] for text in texts]])]
    test.source=lambda:sheets
    public,new_report,new_detail=test.build()
    report.clear();report.update(new_report);detail.clear();detail.update(new_detail)
    if binary_profile:(server.DATA/'informe.dpapi').write_bytes(server.protect(json.dumps({'report':report,'details':detail}).encode()))
    remote.update(dictionary=copy.deepcopy(rules.EMPTY),expected_dictionary=rules.digest(rules.EMPTY))
    remote['statistics']['2025']=public;server.write_json(path,remote)
    page.locator('#technicalRefresh').click()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("revisión 1.")')
    page.locator('#mechanicalSearch').fill('EXTREMO');page.locator('#mechanicalState').select_option('')
    item=page.locator('#mechanicalExpressions>details').filter(has=page.locator('summary',has_text='EXTREMO ·')).first
    item.locator('summary').click();item.get_by_role('button',name='Ver registros originales',exact=True).click()
    item.locator('article').first.get_by_role('button',name='CLASIFICAR EXPRESIÓN',exact=True).click()
    page.wait_for_selector('#dictionaryMeaning')
    page.locator('#dictionaryMeaning').select_option('descriptor')
    form=page.locator('.dictionary-editor');scope=form.get_by_label('Alcance',exact=True)
    scope.select_option('general')
    assert form.get_by_label('Componente ya reconocido',exact=True).is_hidden()
    form.get_by_label('Variantes (separadas por /)',exact=True).fill('EXTREMOS')
    form.get_by_label('Expresión técnica',exact=True).fill('EXTREMO')
    form.get_by_label('Significado del descriptor',exact=True).select_option('extremo')
    preview=form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True)
    preview.click();page.wait_for_selector('.dictionary-preview:not([hidden])')
    assert '9 controles conservados' in form.inner_text()
    assert '7 registros potencialmente afectados' in form.inner_text()
    assert 'Menciones sin clasificar: 11 → 4' in form.inner_text()
    ambiguity=form.locator('.dictionary-preview details').nth(1)
    assert '(3)' in ambiguity.locator('summary').inner_text()
    ambiguity.locator('summary').click();ambiguity.get_by_role('button',name='Ver registros',exact=True).click()
    assert 'EXTREMO BARRA LARGA; EXTREMOS' in ambiguity.inner_text()
    # Cambiar alcance o variantes invalida la autorización de guardar.
    scope.select_option('componente');assert form.locator('.dictionary-preview').is_hidden()
    assert form.get_by_label('Componente ya reconocido',exact=True).is_visible()
    scope.select_option('general');preview.click();page.wait_for_selector('.dictionary-preview:not([hidden])')
    form.get_by_label('Variantes (separadas por /)',exact=True).fill('EXTREMOS ')
    assert form.locator('.dictionary-preview').is_hidden()
    preview.click();page.wait_for_selector('.dictionary-preview:not([hidden])')
    output=os.environ.get('FTR_SCREENSHOTS')
    for width in (390,900,1280):
        page.set_viewport_size({'width':width,'height':950})
        for theme in ('light','dark'):
            page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,theme)
            if output:form.screenshot(path=str(Path(output)/f'descriptor-general-{width}-{theme}.png'))
    page.set_viewport_size({'width':1280,'height':950})
    form.get_by_role('button',name='GUARDAR REGLA GENERAL',exact=True).click();page.locator('#dialogConfirm').click()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("Orden guardada")')
    order=api(page,'orders')['value']['orders'][-1];row=order['statistical']['reglas'][0]
    assert row['alcance']=='general' and row['variantes']==['extremos']
    assert 'componente' not in row and 'categoria' not in row
    assert api(page,'orders/cancel',{'request_id':order['id']})['status']==200
    # Reapertura desde la lista global, incluida la variante y el alcance.
    remote['dictionary']=rules.proposed(rules.EMPTY,[row],rules.digest(rules.EMPTY))
    remote['expected_dictionary']=rules.digest(remote['dictionary']);server.write_json(path,remote)
    page.locator('#technicalRefresh').click()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("revisión 2.")')
    page.locator('#confirmedRules').evaluate('(d)=>d.open=true')
    assert 'CUALQUIER COMPONENTE RECONOCIDO' in page.locator('#technicalRules').inner_text()
    assert 'extremo / extremos' in page.locator('#technicalRules').inner_text()
    page.locator('#technicalRules').get_by_role('button',name='Modificar',exact=True).click()
    form=page.locator('.dictionary-editor')
    assert form.get_by_label('Alcance',exact=True).input_value()=='general'
    assert form.get_by_label('Componente ya reconocido',exact=True).is_hidden()
    assert form.get_by_label('Variantes (separadas por /)',exact=True).input_value()=='extremos'
    form.get_by_role('button',name='CANCELAR',exact=True).click()
