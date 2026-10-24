"""Incidencias KIT en NOVEDADES; nunca usa KIT DESMONTAJE ni infiere ESTADO."""
import re

WORD=re.compile(r'(?<![^\W_])kit(?![^\W_])',re.I)
# Se retiran únicamente la referencia y las fórmulas confirmadas. Cualquier
# defecto desconocido que la acompañe permanece en el análisis mecánico.
PHRASE=re.compile(r'(?<![^\W_])(?:(?:no\s+coincide(?:n)?|no\s+tiene|no|sin)\s+)?kit(?![^\W_])(?:[\s_]+sube\b)?(?:\s+(?:no\s+(?:coincide(?:n)?|funciona)|incorrect[oa]|mal|roto)\b)?(?:\s*(?:n[°º.]?\s*)?\d+\b)?',re.I)

def detected(event):
    return bool(event.get('tiene_novedades') and WORD.search(event.get('novedades','')))

def mechanical_text(text):
    # Conservar las posiciones del texto para la revisión privada por fragmentos.
    return PHRASE.sub(lambda m:' '*len(m.group()),text)

def aggregate(events,lines,pending=False):
    rows=[]
    for line in lines:
        selected=[e for e in events if e['linea']==line['linea']]
        covered=sum(bool(e.get('tiene_novedades')) for e in selected)
        count=sum(detected(e) for e in selected)
        rows.append(dict(linea=line['linea'],controles=line['registros_periodo'],
            con_novedades=None if pending else covered,incidencias=None if pending else count))
    return dict(version=1,estado='pendiente' if pending else 'parcial' if any(r['con_novedades']<r['controles'] for r in rows) else 'disponible',
        controles_con_incidencia=None if pending else sum(r['incidencias'] for r in rows),lineas=rows)

def validate(value,lines):
    def exact(v,keys):
        if not isinstance(v,dict) or set(v)!=set(keys):raise ValueError('Esquema KIT no válido.')
    exact(value,('version','estado','controles_con_incidencia','lineas'))
    if type(value['version']) is not int or value['version']!=1 or value['estado'] not in ('pendiente','parcial','disponible') or not isinstance(value['lineas'],list):raise ValueError('Estadística KIT no válida.')
    if len(value['lineas'])!=len(lines):raise ValueError('Líneas KIT incompletas.')
    pending=value['estado']=='pendiente'
    for row,line in zip(value['lineas'],lines):
        exact(row,('linea','controles','con_novedades','incidencias'))
        if any(type(row[k]) is not int for k in ('linea','controles')) or row['linea']!=line['linea'] or row['controles']!=line['registros_periodo']:raise ValueError('Controles KIT incompatibles.')
        if pending:
            if row['incidencias'] is not None or row['con_novedades'] is not None:raise ValueError('KIT pendiente no puede mostrar ceros.')
        elif any(type(row[k]) is not int for k in ('con_novedades','incidencias')) or not 0<=row['incidencias']<=row['con_novedades']<=row['controles']:raise ValueError('Cantidad KIT inválida.')
    if pending:
        if value['controles_con_incidencia'] is not None:raise ValueError('KIT pendiente no puede mostrar cero.')
    elif type(value['controles_con_incidencia']) is not int or value['controles_con_incidencia']!=sum(r['incidencias'] for r in value['lineas']) or (value['estado']=='parcial')!=any(r['con_novedades']<r['controles'] for r in value['lineas']):raise ValueError('Total o cobertura KIT incompatibles.')
    return value
