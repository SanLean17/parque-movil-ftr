"""Contrato separado de órdenes administrativas; no contiene datos de fiscalizaciones."""
import re
from . import dictionary_rules as rules
from _ftr_pruebas.planilla_anual import spreadsheet_id

WORKFLOW='ftr_estadisticas_admin.yml'
ACTIONS=('dictionary-save','history-import','history-review','history-recalculate')
def clean(action,data):
    if not isinstance(data,dict):raise ValueError('Orden estadística inválida.')
    if action=='dictionary-save':
        if set(data)!={'expected_dictionary','reglas'} or not re.fullmatch('[a-f0-9]{64}',str(data['expected_dictionary'])):raise ValueError('Revisá la versión del diccionario.')
        value=rules.validate(dict(version=1,revision=1,reglas=data['reglas']))
        return {'expected_dictionary':data['expected_dictionary'],'reglas':value['reglas']}
    if action in ('history-import','history-review','history-recalculate'):
        keys={'period','sheetUrl','allow_partial'}
        if action!='history-import':keys|={'expected_archive','expected_dictionary'}
        if action=='history-recalculate':keys|={'expected_records','expected_result'}
        if set(data)!=keys or type(data['period']) is not int or not 2000<=data['period']<=2100 or type(data['allow_partial']) is not bool:raise ValueError('Operación histórica inválida.')
        for key in keys-{'period','sheetUrl','allow_partial'}:
            if not isinstance(data[key],str) or not re.fullmatch('[a-f0-9]{64}',data[key]):raise ValueError('Huella de revisión inválida.')
        identifier=spreadsheet_id(data['sheetUrl'])
        return dict(data,sheetUrl=f'https://docs.google.com/spreadsheets/d/{identifier}/edit')
    raise ValueError('Acción estadística no permitida.')
