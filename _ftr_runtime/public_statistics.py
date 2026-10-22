"""Proyección agregada y verificable del mismo modelo validado por Administración."""
import json
from collections import Counter
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

from _ftr_admin.estadisticas_periodo import clasificar_estado
from .anomalies import CATEGORIES, VERSION, classify
from .config import enabled

FILE = 'estadisticas_ftr.json'
ASSETS = ('estadisticas.html', 'ftr-estadisticas.css', 'ftr-estadisticas.js', FILE)
STATUS = ('fuera_de_servicio', 'observado', 'sin_novedad', 'estado_vacio', 'estado_otro')
TOTALS = ('registros_validos', 'unidades_unicas_por_linea', 'unidades_repetidas',
          'registros_fuera_de_servicio', 'registros_observados', 'registros_sin_novedad',
          'registros_sin_estado', 'registros_otro_estado')
LINE_FIELDS = ('linea', 'registros_periodo', 'dominios_unicos', 'unidades_repetidas', *STATUS)
MINIMUM = 20  # Criterio descriptivo visible, no significación estadística.


def ranking(lines):
    result = {}
    for field in ('fuera_de_servicio', 'observado', 'registros_periodo'):
        top = max((r[field] for r in lines), default=0)
        result[field] = dict(cantidad=top, lineas=[r['linea'] for r in lines if r[field] == top] if top else [])
    return result


def proportions(lines):
    rows = [dict(linea=r['linea'], fuera_de_servicio=r['fuera_de_servicio'], controles=r['registros_periodo'],
                 porcentaje=((2000*r['fuera_de_servicio']+r['registros_periodo'])//(2*r['registros_periodo']))/10 if r['registros_periodo'] else None,
                 muestra_suficiente=r['registros_periodo'] >= MINIMUM) for r in lines]
    return sorted(rows, key=lambda r: (-Fraction(r['fuera_de_servicio'], r['controles']) if r['controles'] else 1, -r['controles'], r['linea']))


def monthly(events, period, cutoff):
    counts = Counter(e['fecha'].month for e in events)
    return [dict(mes=m, controles=counts[m], estado='futuro' if (period,m) > (cutoff.year,cutoff.month) else
                 'en_curso' if (period,m) == (cutoff.year,cutoff.month) else 'completo') for m in range(1,13)]


def mechanics(events, pending=False):
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
    private = []
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
        known, unknown = classify(e['novedades'])
        state = clasificar_estado(e.get('estado'))
        for _, component, _ in known:
            components[component]['cantidad'] += 1
            components[component]['estados'][state] += 1
        components['sin_clasificar']['cantidad'] += len(unknown)
        components['sin_clasificar']['estados'][state] += len(unknown)
        if unknown:
            private.append({k:e.get(k) for k in ('linea','pestana_posicion','fila')} | {'expresiones':unknown})
    for category in categories:
        category['cantidad'] = sum(c['cantidad'] for c in category['componentes'])
    result['identificadas'] = sum(c['cantidad'] for c in categories if c['id'] != 'otras')
    result['sin_clasificar'] = components['sin_clasificar']['cantidad']
    if result['cobertura']['sin_columna']:
        result['estado'] = 'parcial'
    return result, private


def build(report, events, config, read_utc, *, pending_mechanics=False):
    if not report.get('listo_para_revision_de_integracion') or report.get('estadisticas_version') != 4 or report['periodo'] != config['period']:
        raise ValueError('Las estadísticas públicas requieren un informe válido del período configurado.')
    cutoff = datetime.fromisoformat(read_utc).astimezone(ZoneInfo('America/Argentina/Buenos_Aires')).date()
    events = [e for e in events if e.get('linea') in enabled(config) and e.get('dominio') and
              e.get('fecha') and e['fecha'].year == config['period'] and e['fecha'] <= cutoff]
    lines = [{k:r[k] for k in LINE_FIELDS} for r in sorted(report['estadisticas'], key=lambda r:r['linea'])]
    if [r['linea'] for r in lines] != sorted(enabled(config)):
        raise ValueError('Las líneas del informe no coinciden con la configuración.')
    for row in lines:
        group = [e for e in events if e['linea'] == row['linea']]
        domains = Counter(e['dominio'] for e in group)
        if (len(group),len(domains),sum(n>1 for n in domains.values())) != (row['registros_periodo'],row['dominios_unicos'],row['unidades_repetidas']):
            raise ValueError('El historial y el informe estadístico no corresponden a la misma lectura.')
        if not pending_mechanics:
            counts = Counter(clasificar_estado(e.get('estado')) for e in group)
            if any(counts[k] != row[k] for k in STATUS):
                raise ValueError('Los resultados formales de las estadísticas no coinciden.')
    anomalies, private = mechanics(events, pending_mechanics)
    data = dict(version=1, periodo=config['period'], lectura_planilla_utc=read_utc, corte_fecha=cutoff.isoformat(),
        origen='informe_validado_historial' if pending_mechanics else 'lectura_validada',
        totales={k:report['totales_estadisticas'][k] for k in TOTALS}, lineas=lines,
        mensual=monthly(events,config['period'],cutoff), destacados=ranking(lines),
        minimo_controles_proporcion=MINIMUM, proporciones=proportions(lines), anomalias=anomalies)
    validate(data)
    return data, private


def validate(data):
    """Esquema cerrado: nunca serializar texto de entrada ni registros individuales."""
    def exact(value, keys):
        if not isinstance(value,dict) or set(value) != set(keys):
            raise ValueError('Esquema de estadísticas públicas no válido.')
    def number(n):
        if type(n) is not int or n < 0:
            raise ValueError('Cantidad estadística inválida.')
    exact(data, ('version','periodo','lectura_planilla_utc','corte_fecha','origen','totales','lineas','mensual','destacados','minimo_controles_proporcion','proporciones','anomalias'))
    if data['version'] != 1 or type(data['periodo']) is not int or not 2000 <= data['periodo'] <= 2100 or data['origen'] not in ('informe_validado_historial','lectura_validada'):
        raise ValueError('Versión estadística no admitida.')
    stamp = datetime.fromisoformat(data['lectura_planilla_utc'])
    if stamp.tzinfo is None or date.fromisoformat(data['corte_fecha']) != stamp.astimezone(ZoneInfo('America/Argentina/Buenos_Aires')).date():
        raise ValueError('Fecha de lectura estadística inválida.')
    totals=data['totales']; exact(totals,TOTALS)
    for n in totals.values():number(n)
    mapping=dict(registros_validos='registros_periodo',unidades_unicas_por_linea='dominios_unicos',unidades_repetidas='unidades_repetidas',
        registros_fuera_de_servicio='fuera_de_servicio',registros_observados='observado',registros_sin_novedad='sin_novedad',registros_sin_estado='estado_vacio',registros_otro_estado='estado_otro')
    lines=data['lineas']
    for row in lines:
        exact(row,LINE_FIELDS)
        for n in row.values():number(n)
        if not row['linea'] or sum(row[k] for k in STATUS) != row['registros_periodo'] or not 0 <= row['unidades_repetidas'] <= min(row['dominios_unicos'], row['registros_periodo']-row['dominios_unicos']):
            raise ValueError('Resultados estadísticos incompatibles.')
    if [r['linea'] for r in lines] != sorted({r['linea'] for r in lines}) or any(totals[k] != sum(r[v] for r in lines) for k,v in mapping.items()):
        raise ValueError('Totales estadísticos incompatibles.')
    months=data['mensual']
    if len(months)!=12 or [m['mes'] for m in months] != list(range(1,13)):
        raise ValueError('Meses estadísticos inválidos.')
    for m in months:
        exact(m,('mes','controles','estado'));number(m['controles'])
        cutoff=date.fromisoformat(data['corte_fecha'])
        expected='futuro' if (data['periodo'],m['mes'])>(cutoff.year,cutoff.month) else 'en_curso' if (data['periodo'],m['mes'])==(cutoff.year,cutoff.month) else 'completo'
        if m['estado']!=expected or m['estado']=='futuro' and m['controles']:
            raise ValueError('Mes futuro incompatible.')
    if sum(m['controles'] for m in months)!=totals['registros_validos'] or data['destacados']!=ranking(lines) or data['minimo_controles_proporcion']!=MINIMUM or data['proporciones']!=proportions(lines):
        raise ValueError('Gráficos estadísticos incompatibles.')
    a=data['anomalias'];exact(a,('version_reglas','estado','identificadas','sin_clasificar','cobertura','categorias'))
    if a['version_reglas']!=VERSION or a['estado'] not in ('pendiente','parcial','disponible'):
        raise ValueError('Análisis mecánico no válido.')
    pending=a['estado']=='pendiente'
    exact(a['cobertura'],('registros_validos','con_columna','con_texto','vacios','sin_columna'))
    if [c['id'] for c in a['categorias']]!=list(CATEGORIES):raise ValueError('Categorías inválidas.')
    values=[a['identificadas'],a['sin_clasificar'],*a['cobertura'].values()]
    for category in a['categorias']:
        exact(category,('id','cantidad','componentes'));values.append(category['cantidad'])
        if [c['id'] for c in category['componentes']]!=list(CATEGORIES[category['id']]):raise ValueError('Componentes inválidos.')
        for c in category['componentes']:
            exact(c,('id','cantidad','estados'));exact(c['estados'],STATUS)
            values += [c['cantidad'],*c['estados'].values()]
            if not pending and sum(c['estados'].values())!=c['cantidad']:raise ValueError('Estados de anomalías incompatibles.')
        if not pending and sum(c['cantidad'] for c in category['componentes'])!=category['cantidad']:raise ValueError('Categoría incompatible.')
    if pending:
        if any(v is not None for v in values):raise ValueError('Análisis pendiente con cifras inventadas.')
    else:
        for v in values:number(v)
        cov=a['cobertura']
        if cov['registros_validos']!=totals['registros_validos'] or cov['con_columna']+cov['sin_columna']!=cov['registros_validos'] or cov['con_texto']+cov['vacios']!=cov['con_columna']:
            raise ValueError('Cobertura incompatible.')
        if a['identificadas']!=sum(c['cantidad'] for c in a['categorias'] if c['id']!='otras') or a['sin_clasificar']!=a['categorias'][-1]['cantidad']:
            raise ValueError('Totales mecánicos incompatibles.')
        if (a['estado']=='parcial') != bool(cov['sin_columna']):raise ValueError('Disponibilidad mecánica incompatible.')
    return data


def write(root, data):
    validate(data)
    target=Path(root)/FILE
    temp=target.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
    temp.replace(target)
