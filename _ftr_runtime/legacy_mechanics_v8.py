"""Immutable replay of engine 8 protected reports."""
import json
from .legacy_anomalies_v8 import analyze,fold
from .legacy_catalogue_v5 import VERSION,CATEGORIES,ENGINE_REVISION
from .public_statistics import STATUS
from _ftr_admin.estadisticas_periodo import clasificar_estado

def mechanics(events, pending=False, dictionary=None, corrections=None, analyzer=None):
    from .dictionary_rules import compile_rules, EMPTY
    custom=compile_rules(dictionary or EMPTY)
    categories = []
    for category, components in CATEGORIES.items():
        categories.append(dict(id=category, cantidad=None if pending else 0,
            componentes=[dict(id=c, cantidad=None if pending else 0, estados={k:None if pending else 0 for k in STATUS}) for c in components]))
    result = dict(version_reglas=VERSION, estado='pendiente' if pending else 'disponible',
        identificadas=None if pending else 0, sin_clasificar=None if pending else 0,
        cobertura={k:None if pending else 0 for k in ('registros_validos','con_columna','con_texto','vacios','sin_columna')}, categorias=categories)
    result['motor_revision']=ENGINE_REVISION
    result['elementos_fisicos']={k:None if pending else 0 for k in ('cantidad_confirmada','menciones_con_cantidad','menciones_sin_cantidad')}
    if pending:
        return result, []
    components = {c['id']:c for category in categories for c in category['componentes']}
    private = {}; references = []
    for e in events:
        coverage = result['cobertura']; coverage['registros_validos'] += 1
        if not e.get('tiene_novedades'):
            coverage['sin_columna'] += 1
            continue
        coverage['con_columna'] += 1
        if not e.get('novedades', '').strip():
            coverage['vacios'] += 1
            continue
        coverage['con_texto'] += 1
        if analyzer:
            analysis=analyzer(e)
        elif corrections:
            from .record_interpretation import apply as interpret_record
            analysis = interpret_record(e,corrections,dictionary or EMPTY)
        else:analysis = analyze(e['novedades'],custom)
        known, unknown = analysis['hallazgos'], analysis['pendientes']
        state = clasificar_estado(e.get('estado'))
        for finding in known:
            component = finding['componente']
            components[component]['cantidad'] += 1
            physical=result['elementos_fisicos'];quantity=finding.get('cantidad_fisica')
            if quantity is None:physical['menciones_sin_cantidad']+=1
            else:
                physical['menciones_con_cantidad']+=1;physical['cantidad_confirmada']+=quantity
            components[component]['estados'][state] += 1
        components['sin_clasificar']['cantidad'] += len(unknown)
        components['sin_clasificar']['estados'][state] += len(unknown)
        ref = {k:e.get(k) for k in ('linea','pestana','pestana_posicion','fila')}
        ref.update(periodo=e['fecha'].year, novedades_original=e['novedades'])
        ref.update(fecha=e['fecha'].isoformat(),dominio=e.get('dominio'),interno=e.get('interno'),estado_formal=e.get('estado_original',e.get('estado')),resultado=state)
        import hashlib
        ref['registro_id']=hashlib.sha256(json.dumps([ref.get(k) for k in ('periodo','linea','fecha','dominio','interno','pestana','fila','novedades_original')],ensure_ascii=False).encode()).hexdigest()
        for expression in unknown:
            item = private.setdefault((e['fecha'].year,fold(expression)), dict(periodo=e['fecha'].year, expresion=expression,
                variantes=[], frecuencia=0, estado='pendiente', estados={k:0 for k in STATUS}, referencias=[]))
            item['frecuencia'] += 1; item['referencias'].append(ref)
            item['estados'][state] += 1
            if expression not in item['variantes']:item['variantes'].append(expression)
        references.extend(ref | finding for finding in known if finding['referencia'])
    for category in categories:
        category['cantidad'] = sum(c['cantidad'] for c in category['componentes'])
    result['identificadas'] = sum(c['cantidad'] for c in categories if c['id'] != 'otras')
    result['sin_clasificar'] = components['sin_clasificar']['cantidad']
    if result['cobertura']['sin_columna']:
        result['estado'] = 'parcial'
    return result, dict(version_reglas=VERSION, pendientes=list(private.values()), referencias_tecnicas=references)

