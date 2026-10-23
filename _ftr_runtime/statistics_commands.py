"""Contrato separado de órdenes administrativas; no contiene datos de fiscalizaciones."""
import re
from . import dictionary_rules as rules
from _ftr_pruebas.planilla_anual import spreadsheet_id

WORKFLOW='ftr_estadisticas_admin.yml'
def clean(action,data):
    if not isinstance(data,dict):raise ValueError('Orden estadística inválida.')
    if action=='dictionary-save':
        if set(data)!={'expected_dictionary','reglas'} or not re.fullmatch('[a-f0-9]{64}',str(data['expected_dictionary'])):raise ValueError('Revisá la versión del diccionario.')
        value=rules.validate(dict(version=1,revision=1,reglas=data['reglas']))
        return {'expected_dictionary':data['expected_dictionary'],'reglas':value['reglas']}
    if action=='history-import':
        if set(data)!={'period','sheetUrl','allow_partial'} or type(data['period']) is not int or not 2000<=data['period']<=2100 or type(data['allow_partial']) is not bool:raise ValueError('Importación histórica inválida.')
        identifier=spreadsheet_id(data['sheetUrl'])
        return dict(period=data['period'],sheetUrl=f'https://docs.google.com/spreadsheets/d/{identifier}/edit',allow_partial=data['allow_partial'])
    raise ValueError('Acción estadística no permitida.')
