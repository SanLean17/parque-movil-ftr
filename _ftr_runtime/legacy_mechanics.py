"""Replay of engines 5/6 for integrity checks of existing protected reports only."""
import json
from .legacy_catalogue_v3 import VERSION,CATEGORIES
from .legacy_anomalies_v6 import fold
from .public_statistics import STATUS
from _ftr_admin.estadisticas_periodo import clasificar_estado

def mechanics(events, dictionary, revision):
    if revision==10:
        from .legacy_mechanics_v10 import mechanics as previous
        return previous(events,dictionary=dictionary)
    if revision==9:
        from .legacy_mechanics_v9 import mechanics as previous
        return previous(events,dictionary=dictionary)
    if revision==8:
        from .legacy_mechanics_v8 import mechanics as previous
        return previous(events,dictionary=dictionary)
    if revision==7:
        from .legacy_mechanics_v7 import mechanics as previous
        return previous(events,dictionary=dictionary)
    pending=False;corrections=None
    from . import legacy_anomalies_v5, legacy_anomalies_v6
    analyze=(legacy_anomalies_v5 if revision==5 else legacy_anomalies_v6).analyze
    from .dictionary_rules import compile_rules, EMPTY
    custom=compile_rules(dictionary or EMPTY)
    categories = []
    for category, components in CATEGORIES.items():
        categories.append(dict(id=category, cantidad=None if pending else 0,
            componentes=[dict(id=c, cantidad=None if pending else 0, estados={k:None if pending else 0 for k in STATUS}) for c in components]))
    result = dict(version_reglas=VERSION, estado='pendiente' if pending else 'disponible',
        identificadas=None if pending else 0, sin_clasificar=None if pending else 0,
        cobertura={k:None if pending else 0 for k in ('registros_validos','con_columna','con_texto','vacios','sin_columna')}, categorias=categories)
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
        if corrections:
            from .record_interpretation import apply as interpret_record
            analysis = interpret_record(e,corrections,dictionary or EMPTY)
        else:analysis = analyze(e['novedades'],custom)
        known, unknown = analysis['hallazgos'], analysis['pendientes']
        state = clasificar_estado(e.get('estado'))
        for finding in known:
            component = finding['componente']
            components[component]['cantidad'] += 1
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
