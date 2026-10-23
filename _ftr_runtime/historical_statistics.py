"""Importación explícita de años cerrados. Nunca escribe controlados/parques/configuración."""
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from _ftr_admin import diagnostico_administrativo as admin
from _ftr_admin.estadisticas_periodo import completar_estadisticas
from . import public_statistics as stats, statistics_archive as archive

class HistoricalValidationError(ValueError):
    def __init__(self,message,report,detail):
        super().__init__(message)
        self.report,self.detail=report,detail

def build(sheets, period, source_id, read_utc, dictionary, *, allow_partial=False):
    base=admin.base
    today=datetime.fromisoformat(read_utc).astimezone(ZoneInfo('America/Argentina/Buenos_Aires')).date()
    if type(period) is not int or not 2000<=period<today.year:raise ValueError('Solo se importan años cerrados.')
    events=list(admin.source_rows(sheets,include_novedades=True))
    # Fechas reales acreditan el año. Una hoja vacía no confirma por sí sola su período.
    if not any(e['fecha'] and e['fecha'].year==period for e in events):raise ValueError('La fuente no contiene fechas del período solicitado.')
    numbers={e['linea'] for e in events if e['linea']}
    for sheet in sheets:
        if base.is_control_sheet(sheet.name):
            for block in base.blocks(sheet):numbers.update(block['ids'])
    configured={n:None for n in sorted(numbers)}
    report,records=base.analyze(sheets,configured,period,today=today)
    blocking={'ENCABEZADOS_NO_ENCONTRADOS','BLOQUE_MULTIPLE_SIN_COLUMNA_LINEA','TABLA_SIN_IDENTIDAD','TITULO_Y_PESTANA_NO_COINCIDEN'}
    if blocking.intersection(report['avisos_por_tipo']) or report['lineas_habilitadas_no_encontradas']:
        raise ValueError('Hay tablas históricas sin identificar. Se requiere corregir su estructura antes de publicar.')
    with tempfile.TemporaryDirectory(prefix='ftr-historico-') as temp:
        root=Path(temp)
        base.add_comparison(report,records,root)
        detail=admin.extend_report(report,sheets,root,configured,source_id,read_utc,today=today,source_events=events)
    completar_estadisticas(report,events,today)
    excluded=len(events)-report['totales_estadisticas']['registros_validos']
    report.update(historico=True,inicio_lectura_utc=read_utc,fin_prueba_utc=read_utc,
                  revision_repositorio=detail['revision_repositorio'],excluidos_importacion=excluded)
    if excluded and not allow_partial:
        detail['historico']=True
        report['listo_para_revision_de_integracion']=False
        raise HistoricalValidationError(f'Hay {excluded} registros excluidos por fecha, dominio o línea. Revisá la fuente o autorizá explícitamente una importación parcial.',report,detail)
    config={'period':period,'lines':[{'line':n,'company':None,'enabled':True} for n in configured]}
    data,unknown=stats.build(dict(report,listo_para_revision_de_integracion=True),events,config,read_utc,dictionary=dictionary)
    data['origen']='importacion_historica'
    data['calidad']={'parcial':bool(excluded),'registros_excluidos':excluded}
    stats.validate(data)
    detail['novedades_sin_clasificar']=unknown
    detail['historico']=True
    return data,report,detail

def add_archive(root,data):
    """Solo agrega un año nuevo; una revisión requiere otro procedimiento explícito."""
    root=Path(root);stats.validate(data)
    index=archive.validate_collection(root)
    year=data['periodo']
    if year>=json.loads((root/stats.FILE).read_bytes())['periodo']:raise ValueError('El importador no puede cambiar el período activo.')
    target=root/f'estadisticas/{year}.json'
    if target.exists() or any(r['periodo']==year for r in index['periodos']):raise ValueError('Ese año ya está archivado. No se sobrescribe sin una revisión histórica explícita.')
    body=archive.encoded(data)
    index['periodos'].append(archive.entry(data,body));index['periodos'].sort(key=lambda r:r['periodo'],reverse=True)
    archive.validate_index(index)
    target.write_bytes(body);(root/stats.INDEX).write_bytes(archive.encoded(index))
    archive.validate_collection(root)
    return [f'estadisticas/{year}.json',stats.INDEX]
