"""Version 7 browser contract, also run against the newly compiled Windows EXE."""
import copy
import json
import os
from datetime import date
from pathlib import Path
from _ftr_runtime import dictionary_rules as rules, public_statistics as stats
from _ftr_runtime.test_technical_v7 import CASES
from _ftr_runtime.legacy_mechanics import mechanics
from statistics_browser_checks import api


def check_technical_v7(page,server,test,path,remote,report,detail,binary_profile):
    texts=list(CASES)+['amortiguador.3','amortiguador-3','EXTREMO','BARRA LARGA EXTREMO BARRA CORTA']
    test.source=lambda:[test.sheet('Línea 999',[['FECHA','DOMINIO','INTERNO','ESTADO','NOVEDADES'],
        *[['01/02/2025','AA111AA',7,'SIN NOVEDAD',text] for text in texts]])]
    general=dict(expresion='extremo',variantes=['extremos'],tipo='descriptor',significado='extremo',alcance='general',habilitada=True)
    dictionary=rules.validate(dict(version=1,revision=4,reglas=[general]))
    public,new_report,new_detail=test.build(dictionary)
    capsule=new_detail['novedades_sin_clasificar']['revision_mecanica'];capsule['motor_revision']=6
    events=[dict(r,fecha=date.fromisoformat(r['fecha'])) for r in capsule['registros']]
    public['anomalias'],private=mechanics(events,dictionary,6)
    capsule['estadisticas']['anomalias']=copy.deepcopy(public['anomalias'])
    new_detail['novedades_sin_clasificar'].update(private)
    report.clear();report.update(new_report);detail.clear();detail.update(new_detail)
    if binary_profile:(server.DATA/'informe.dpapi').write_bytes(server.protect(json.dumps({'report':report,'details':detail}).encode()))
    remote.update(dictionary=dictionary,expected_dictionary=rules.digest(dictionary))
    remote['statistics']['2025']=public;server.write_json(path,remote)
    page.locator('#technicalRefresh').click()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("revisión 4.")')
    page.locator('#mechanicalSearch').fill('')
    assert page.locator('#mechanicalExpressions .dictionary-state.waiting').count()>0
    assert page.locator('#mechanicalExpressions .dictionary-state.attention').count()>0
    page.locator('#dictionaryApplication summary').click()
    assert 'Actualizar Drive' in page.locator('#dictionaryApplication').inner_text()
    assert 'Preparar revisión histórica' in page.locator('#dictionaryApplication').inner_text()

    def open_record(text):
        page.locator('#dictionaryReview').evaluate('(d)=>d.open=true')
        page.locator('#dictionaryRecordSearch').fill(text);page.locator('#dictionaryFind').click()
        page.wait_for_selector('#dictionaryRecords article')
        card=page.locator('#dictionaryRecords article').first
        card.get_by_role('button',name='CLASIFICAR EXPRESIÓN',exact=True).click()
        page.wait_for_selector('#dictionaryMeaning');assert page.locator('#dictionaryMeaning').input_value()==''
        return page.locator('.dictionary-editor')

    form=open_record('No coincide Kit')
    assert form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True).count()==0
    page.locator('#dictionaryMeaning').select_option('descriptor')
    form.get_by_label('Expresión técnica',exact=True).fill('No coincide Kit')
    assert form.get_by_label('¿QUÉ INFORMACIÓN AGREGA?',exact=True).input_value()==''
    assert form.get_by_label('Significado del descriptor').input_value()==''
    form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True).click()
    assert 'Seleccioná qué información agrega' in form.inner_text()
    assert form.get_by_role('button',name='GUARDAR REGLA GENERAL',exact=True).count()==0
    form.get_by_role('button',name='CANCELAR',exact=True).click()

    form=open_record('corta pitman')
    page.locator('#dictionaryMeaning').select_option('correction')
    form.get_by_label('Categoría',exact=True).select_option('direccion')
    form.get_by_label('Componente',exact=True).select_option('barra_larga')
    assert form.get_by_label('Componente',exact=True).input_value()=='barra_larga'
    form.get_by_label('Componente',exact=True).select_option('barra_corta')
    form.get_by_label('Parte afectada',exact=True).select_option('lado pitman')
    with page.expect_response('**/api/statistics-preview') as response:
        form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True).click()
    assert response.value.status==200,response.value.json()
    effect=response.value.json();assert effect['registros']==len(texts)
    assert effect['antes']['sin_clasificar']>effect['despues']['sin_clasificar']
    for record in effect['afectados']:
        assert record['estado_formal']=='SIN NOVEDAD'
    controls=form.locator('.dictionary-save')
    assert controls.locator('button').first.inner_text()=='GUARDAR REGLA GENERAL'
    assert controls.evaluate('(e)=>getComputedStyle(e).position')=='sticky'
    form.get_by_role('button',name='GUARDAR REGLA GENERAL',exact=True).click()
    assert 'Confirmación pendiente' in form.inner_text()
    page.locator('#dialogCancel').click()
    # Particular correction uses protected fragments, never sends observation text.
    with page.expect_response('**/api/dictionary-record-preview') as response:
        form.get_by_role('button',name='VISTA PREVIA SOLO ESTE REGISTRO',exact=True).click()
    assert response.value.status==200,response.value.json()
    count=len(api(page,'orders')['value']['orders'])
    form.get_by_role('button',name='GUARDAR SOLO ESTE REGISTRO',exact=True).click();page.locator('#dialogConfirm').click()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("particular guardada")')
    assert len(api(page,'orders')['value']['orders'])==count
    form=open_record('corta pitman');assert 'interpretación particular guardada' in form.inner_text()
    page.locator('#dictionaryMeaning').select_option('pending');form.get_by_role('button',name='CANCELAR',exact=True).click()

    form=open_record('diafragma');page.locator('#dictionaryMeaning').select_option('subcomponent')
    assert form.get_by_label('¿QUÉ INFORMACIÓN AGREGA?',exact=True).input_value()=='subcomponente'
    form.get_by_label('Expresión técnica',exact=True).fill('DIAFRAGMA')
    form.get_by_label('Significado del descriptor').select_option('diafragma')
    assert form.get_by_label('Componente ya reconocido').input_value()=='pulmon_freno'
    with page.expect_response('**/api/statistics-preview') as response:
        form.get_by_role('button',name='VISTA PREVIA DE REGLA GENERAL',exact=True).click()
    assert response.value.status==200,response.value.json()
    for width in (390,900,1280):
        page.set_viewport_size({'width':width,'height':950})
        for theme in ('light','dark'):
            page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            if os.environ.get('FTR_SCREENSHOTS'):form.screenshot(path=str(Path(os.environ['FTR_SCREENSHOTS'])/f'subcomponente-{width}-{theme}.png'))
    page.set_viewport_size({'width':1280,'height':950})
    form.get_by_role('button',name='GUARDAR REGLA GENERAL',exact=True).click();page.locator('#dialogConfirm').click()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("Orden guardada")')
    order=api(page,'orders')['value']['orders'][-1]
    assert dictionary['reglas'][0] in order['statistical']['reglas']  # original EXTREMO rule unchanged
    assert len(order['statistical']['reglas'])==2
    assert 'AA111AA' not in json.dumps(order['statistical'])
    assert api(page,'orders/cancel',{'request_id':order['id']})['status']==200
    # Only a verified matching publication may turn the old resolved items green.
    remote['statistics']['2025']['anomalias']=stats.mechanics(events,dictionary=dictionary)[0]
    remote['publication']['2025']=True;server.write_json(path,remote)
    page.locator('#technicalRefresh').click()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("revisión 4.")')
    page.wait_for_selector('#mechanicalExpressions .dictionary-state.verified',state='attached')
    verified=page.locator('#mechanicalExpressions details').filter(has=page.locator('.dictionary-state.verified')).first
    verified.locator('summary').click();assert verified.locator('.dictionary-state.verified').is_visible()
    assert page.locator('#mechanicalExpressions .dictionary-state.attention').count()>0
    print('Motor 7 UI: corrección libre, subcomponente, campos sin defaults, vista previa completa, guardado cercano, cola ficticia, rojo/amarillo/verde con evidencia, 3 tamaños y 2 temas OK.')
