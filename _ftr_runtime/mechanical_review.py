"""Recálculo local verificable desde un informe cifrado, sin consultar fuentes."""
import copy
import hashlib
import json
from datetime import date
from . import dictionary_rules as rules, public_statistics as stats
from .mechanical_dictionary import ENGINE_REVISION

FIELDS=('linea','pestana','pestana_posicion','fila','dominio','interno','estado','estado_original','tiene_novedades','novedades')

def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def snapshot(events, data, dictionary):
    rows=[{**{k:e.get(k) for k in FIELDS},'fecha':e['fecha'].isoformat()} for e in events]
    return dict(version=1,motor_revision=ENGINE_REVISION,periodo=data['periodo'],registros=rows,diccionario=dictionary,estadisticas=copy.deepcopy(data),huella_registros=fingerprint(rows))

def unpack(value):
    if not isinstance(value,dict) or value.get('version')!=1:raise ValueError('Este informe no conserva los registros necesarios. Abrí un informe nuevo del período.')
    if value.get('motor_revision',3) not in (5,6,7,ENGINE_REVISION):raise ValueError('Este informe usa un motor anterior. Prepará un nuevo informe para calcular el impacto exacto.')
    data=stats.validate(value['estadisticas']);dictionary=rules.validate(value['diccionario'])
    rows=value['registros']
    if value['periodo']!=data['periodo'] or not isinstance(rows,list) or len(rows)>100000 or fingerprint(rows)!=value['huella_registros']:
        raise ValueError('El informe protegido no es íntegro.')
    events=[dict(r,fecha=date.fromisoformat(r['fecha'])) for r in rows]
    if len(events)!=data['totales']['registros_validos'] or any(e['fecha'].year!=data['periodo'] for e in events):raise ValueError('El informe no corresponde al período completo.')
    # Comprueba también estados, ubicación y deduplicación con el mismo motor.
    if value['motor_revision']<ENGINE_REVISION:
        from .legacy_mechanics import mechanics
        baseline,private=mechanics(events,dictionary,value['motor_revision'])
    else:baseline,private=stats.mechanics(events,dictionary=dictionary)
    if baseline!=data['anomalias']:raise ValueError('Este informe usa un motor anterior. Prepará un nuevo informe para calcular el impacto exacto.')
    return events,data,dictionary,private

def preview(value, dictionary, corrections=None):
    events,data,old,_=unpack(value)
    after,private=stats.mechanics(events,dictionary=dictionary,corrections=corrections)
    proposed=copy.deepcopy(data)
    proposed['anomalias']=after
    proposed['interpretacion']={'revision':dictionary['revision'],'sha256':rules.digest(dictionary)}
    stats.validate(proposed)
    from .record_interpretation import reference,apply
    affected=[];ambiguous=[]
    from .anomalies import analyze
    old_compiled=rules.compile_rules(old)
    if value['motor_revision']<ENGINE_REVISION:
        from . import legacy_anomalies_v5,legacy_anomalies_v6,legacy_anomalies_v7
        before_analyze={5:legacy_anomalies_v5,6:legacy_anomalies_v6,7:legacy_anomalies_v7}[value['motor_revision']].analyze
    else:before_analyze=analyze
    def comparable(analysis):
        from .technical_fields import EXTRA_FIELDS
        return dict(analysis,hallazgos=[{**dict.fromkeys(EXTRA_FIELDS),**f} for f in analysis['hallazgos']])
    for event in events:
        before=before_analyze(event.get('novedades',''),old_compiled);result=apply(event,corrections or {},dictionary)
        if comparable(before)!=comparable(result):affected.append(dict(reference(event),antes=before,despues=result))
        unresolved=result['pendientes']
        if unresolved:ambiguous.append(dict(reference(event),pendientes=unresolved,motivo='Texto sin interpretación inequívoca: '+ ' · '.join(unresolved)))
    return dict(periodo=data['periodo'],lectura=data['lectura_planilla_utc'],motor_antes=value['motor_revision'],motor_despues=ENGINE_REVISION,registros=len(events),afectados=affected,ambiguos=ambiguous,
                antes=data['anomalias'],despues=after,huella_registros=value['huella_registros'],
                huella_resultado=fingerprint(after),pendientes=private['pendientes'])

def unchanged_controls(before,after):
    for key in ('periodo','totales','lineas','mensual','destacados','minimo_controles_proporcion','proporciones','calidad'):
        if before.get(key)!=after.get(key):raise ValueError('La fuente cambió controles o resultados originales. La revisión mecánica se detuvo sin publicar.')
