"""Recorrido real del panel con catálogo ficticio y órdenes locales, sin fuentes."""
import copy
from _ftr_runtime import dictionary_rules as rules
from _ftr_runtime.config import load,digest
from _ftr_runtime.mechanical_dictionary import CATEGORIES
from pathlib import Path

def check_statistics_admin(page):
    cfg=load(Path(__file__).resolve().parents[1])
    value=dict(remote=dict(dictionary=copy.deepcopy(rules.EMPTY),expected_dictionary=rules.digest(rules.EMPTY),expected=digest(cfg),period=2026,periods=[2026]),
               catalogue=CATEGORIES,runs=[],pending=[dict(expresion='X12',periodo=2025,frecuencia=2,referencias=[dict(linea=999,pestana_posicion=3,pestana='Línea 999',fila=7)])])
    page.route('**/api/statistics-admin?remote=1',lambda route:route.fulfill(json=value))
    def api(path,body=None):
        return page.evaluate('''async ({path,body})=>{const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-FTR-CSRF':document.querySelector('meta[name="ftr-csrf"]').content},body:body?JSON.stringify(body):undefined});return {status:r.status,value:await r.json()}}''',dict(path=path,body=body))
    def refresh():
        page.locator('#technicalRefresh').click()
        page.wait_for_function('(n)=>document.querySelector("#technicalStatus").textContent.includes("revisión "+n+".")',arg=value['remote']['dictionary']['revision'])
    def submit():
        page.locator('#technicalPublic').check();page.locator('#technicalSave').click();page.locator('#dialogConfirm').click()
        page.wait_for_function('()=>!document.querySelector("#confirmDialog").open')
    def last_order(action):
        orders=api('orders')['value']['orders'];row=orders[-1];assert row['action']==action,row
        assert row['status']=='pending',row
        assert 'referencias' not in row.get('statistical',{})
        result=api('orders/cancel',dict(request_id=row['id']))
        assert result['status']==200,result
        return row
    page.evaluate('showView("source")')
    page.locator('#technicalDictionary summary').first.click();refresh()
    page.locator('#technicalPending summary').first.click()
    assert 'Pestaña 3: Línea 999 · Fila 7' in page.locator('#technicalPending').inner_text()
    page.locator('#technicalPending button').first.click()
    page.locator('#technicalComponent').select_option('barra_larga');submit()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("Orden guardada")')
    row=last_order('dictionary-save');assert row['statistical']['reglas'][0]['expresion']=='x12'
    confirmed=rules.proposed(rules.EMPTY,row['statistical']['reglas'],rules.digest(rules.EMPTY))
    value['remote'].update(dictionary=confirmed,expected_dictionary=rules.digest(confirmed));refresh()
    page.locator('#technicalRules button').first.click()
    page.locator('#technicalComponent').select_option('barra_corta');page.locator('#technicalEnabled').uncheck();submit()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("Orden guardada")')
    row=last_order('dictionary-save');rule=row['statistical']['reglas'][0]
    assert rule['componente']=='barra_corta' and rule['habilitada'] is False
    page.locator('#technicalDiscard').click();page.locator('#technicalExpression').fill('X12');submit()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("CONFLICTO")')
    page.locator('#technicalDiscard').click()
    assert 'sigue protegida' in page.locator('#technicalStatus').inner_text()
    page.locator('#historicalImporter summary').first.click()
    page.locator('#historicalUrl').fill('https://docs.google.com/spreadsheets/d/HISTORICAL_FICTITIOUS_1234567/edit')
    page.locator('#historicalForm button').click();page.locator('#dialogConfirm').click()
    page.wait_for_function('()=>document.querySelector("#technicalStatus").textContent.includes("Importación solicitada")')
    row=last_order('history-import');assert row['statistical']['period']==2025 and not row['statistical']['allow_partial']
    # La incidencia sigue visible aunque el registro sea válido para los conteos.
    page.evaluate('''()=>{incidentCategory='advertencia';adminDetails={version:3,periodo:diagnosticReport.periodo,revision_repositorio:diagnosticReport.revision_repositorio,detectado_utc:diagnosticReport.inicio_lectura_utc,incidencias:[{id:'estado-ficticio',codigo:'CONTROL_SIN_ESTADO',categoria:'advertencia',mensaje:'Fiscalización válida sin resultado en ESTADO.',linea:91,pestana:'Línea 91',pestana_posicion:5,fila:7,celda:'I7',fecha_control:'2026-02-03',dominio_ingresado:'AA111AA',interno:'1'}],repetidos:[]};renderIncidents();showView('incidents')}''')
    assert 'I7' in page.locator('#incidentList').inner_text()
    assert 'CONTROL SIN ESTADO' in page.locator('#incidentList').inner_text()
    page.unroute('**/api/statistics-admin?remote=1')
