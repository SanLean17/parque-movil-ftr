"""Equivalencias confirmadas: datos literales, sin regex ni observaciones privadas."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from .mechanical_dictionary import CATEGORIES
from .technical_fields import INFORMATION, EXTRA_FIELDS, validate_extra

FILE = '_ftr_diccionario.json'
EMPTY = {'version': 1, 'revision': 1, 'reglas': []}
GENERAL = {'falla','fallas','juego','roto','rota','flojo','floja','sin','no','si','ok','mal','bien','estado','novedad','novedades','otro','otros','unidad','vehiculo','coche','interno','dominio','fecha','linea','izquierdo','derecho','delantero','trasero','perdida','aire','aceite'}
TECHNICAL = set('jgo jg b bl bc larga largo corta corto bar barr direccion dir susp suspension tensor tensores amort amortig buje bujes fr freno frenos pulm pulmon valv valvula niv niveladora estabilizadora card cruc cruceta crucetas neum neumatico electr electrico corr corriente bat bateria sonora marcha atras alarma del de la tras delant trasero delantero izq der'.split())
SPECIFIC = TECHNICAL - GENERAL - set('jgo jg b bar barr del de la tras delant izq der'.split())
GENERAL.update('jgo jg bar barr izq der delant tras'.split())
LEGACY_MEANINGS = ('delantero','trasero','derecho','izquierdo','superior','inferior','interno','externo','extremo','juego','flojo','suelto','rotura','desgaste')
MEANINGS = tuple(dict.fromkeys((*LEGACY_MEANINGS,*(v for group in INFORMATION.values() for v in group))))
DESCRIPTORS = set('superior sup inferior inf tras trasero delantero delant del derecho der izquierdo izq interno int externo ext extremo punta juego jgo flojo suelto rotura desgaste'.split())
DESCRIPTORS.update('extremos puntas superiores inferiores derechos derechas derecho derecha izquierdos izquierdas izquierda delanteros delanteras delantera traseros traseras trasera internos internas interna externos externas externa flojos flojas floja sueltos sueltas suelta'.split())

DESCRIPTORS.update(('lado eje','lado pitman','diafragma','zona media','cortado','cortada','cortados','cortadas','pinchado','pinchada','liso','lisa','lisos','lisas','faltante','ausente','carece de','falta','no funciona','suleto','ambos','ambas','dos'))
TECHNICAL.update('pitman brazo lado eje extremo diafragma flexible flexibles estabilizadora chicharra senal neumaticos'.split())
SPECIFIC.update({'pitman','diafragma','chicharra','flexible'})

def general(row):
    return row.get('tipo')=='descriptor' and row.get('alcance')=='general'

def terms(row):
    return [row['expresion'],*row.get('variantes',[])]

def overlap(a,b):
    return any(re.search(r'\b'+re.escape(x)+r'\b',y) or re.search(r'\b'+re.escape(y)+r'\b',x) for x in terms(a) for y in terms(b))

def effective(contextual,component):
    # La regla específica habilitada prevalece para el mismo término literal.
    chosen={r['expresion']:r for r in contextual if general(r)}
    chosen.update({r['expresion']:r for r in contextual if r.get('componente')==component})
    return list(chosen.values())

def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD',value.lower().strip()) if not unicodedata.combining(c))

def expression(value):
    # Frases literales de vocabulario técnico acotado. Nunca texto libre,
    # patentes, identificadores, regex ni instrucciones ejecutables.
    if not isinstance(value,str):raise ValueError('Ingresá una abreviatura técnica general.')
    if any(c in value for c in '\n\r\t'):raise ValueError('La equivalencia debe ocupar una sola línea.')
    value=normalized(value)
    value=re.sub(' +',' ',value)
    words=value.split(' ')
    single=bool(re.fullmatch(r'[a-z]{1,4}[0-9]{1,2}',value) or value in TECHNICAL) and value not in GENERAL
    phrase=2<=len(words)<=5 and len(value)<=48 and all(w in TECHNICAL for w in words) and any(w in SPECIFIC for w in words)
    if not (single or phrase):
        raise ValueError('Usá una abreviatura o hasta cinco palabras del vocabulario técnico, sin datos individuales ni símbolos.')
    if re.fullmatch(r'[ra][0-9]+|p[fs][0-9]*',value):raise ValueError('Los códigos R, A, PF y PS pertenecen al diccionario confirmado original.')
    return value

def validate(value):
    if not isinstance(value,dict) or set(value)!={'version','revision','reglas'} or value['version']!=1 or type(value['revision']) is not int or value['revision']<1 or not isinstance(value['reglas'],list) or len(value['reglas'])>300:
        raise ValueError('Diccionario no válido.')
    from .anomalies import PATTERN, NEUTRAL
    rows=[];seen=[]
    for row in value['reglas']:
        if isinstance(row,dict) and row.get('tipo')=='ortografia':
            from .technical_spelling import validate as spelling
            clean=spelling(row)
            if any(overlap(clean,other) or other.get('corregida')==clean['expresion'] or clean['corregida']==other['expresion'] for _,other in seen):raise ValueError('Corrección duplicada, encadenada o en conflicto.')
            seen.append(('*',clean));rows.append(clean);continue
        contextual=isinstance(row,dict) and row.get('tipo')=='descriptor'
        keys={'expresion','habilitada'}|({'tipo','significado'} if contextual else set())
        if not isinstance(row,dict):raise ValueError('Regla no válida.')
        if not general(row):keys|={'categoria','componente'}
        correction=row.get('tipo')=='correccion'
        optional={'alcance','variantes','informacion'} if contextual else ({'tipo','parte','subcomponente','ubicacion','defecto','cantidad_fisica'} if correction else set())
        if not keys<=set(row) or set(row)-keys-optional:raise ValueError('Regla no válida.')
        if contextual and row.get('alcance','componente') not in ('general','componente'):raise ValueError('Alcance de descriptor no válido.')
        word=normalized(row['expresion']) if contextual and isinstance(row['expresion'],str) else expression(row['expresion'])
        if contextual and (word not in DESCRIPTORS or row['significado'] not in MEANINGS):raise ValueError('Elegí un descriptor técnico y su significado, sin datos individuales.')
        if contextual and 'informacion' in row:
            kind=row['informacion']
            if kind not in INFORMATION or row['significado'] not in INFORMATION[kind]:raise ValueError('El significado no corresponde al tipo de información elegido.')
            if kind=='subcomponente' and (general(row) or row.get('componente')!='pulmon_freno'):raise ValueError('Confirmá el componente del subcomponente: diafragma pertenece al pulmón de freno.')
        if correction:
            if len(word.split())<2 or not PATTERN.search(word):raise ValueError('La corrección general requiere una frase técnica completa con componente identificable.')
            validate_extra(row)
            from .record_interpretation import LOCATIONS,DEFECTS
            if row.get('ubicacion','sin_ubicacion') not in LOCATIONS or row.get('defecto','no_identificado') not in DEFECTS:raise ValueError('Revisá ubicación y defecto de la corrección.')
        clean=dict(row,expresion=word)
        if 'variantes' in row:
            variants=row['variantes']
            if not isinstance(variants,list) or len(variants)>8 or any(not isinstance(v,str) or normalized(v) not in DESCRIPTORS for v in variants):raise ValueError('Usá hasta ocho variantes del vocabulario de descriptores técnicos.')
            variants=[normalized(v) for v in variants]
            if len(set(variants))!=len(variants):raise ValueError('Las variantes no deben repetirse.')
            clean['variantes']=sorted(v for v in variants if v!=word)
        scope=('general' if general(row) else row['componente']) if contextual else '*'
        if any((scope==s or '*' in (scope,s)) and overlap(clean,other) for s,other in seen):raise ValueError('Expresión duplicada, superpuesta o en conflicto; modificá la regla existente.')
        if not contextual and not correction and (PATTERN.search(word) or NEUTRAL.fullmatch(word)):raise ValueError('La expresión ya está definida por las reglas originales.')
        if type(row['habilitada']) is not bool or (not general(row) and (row['categoria'] not in CATEGORIES or row['componente'] not in CATEGORIES[row['categoria']])):
            raise ValueError('La categoría y el componente no coinciden.')
        if contextual and row.get('categoria')=='otras':raise ValueError('Un descriptor requiere un componente reconocido.')
        seen.append((scope,clean));rows.append(clean)
    return dict(version=1,revision=value['revision'],reglas=sorted(rows,key=lambda r:(r['expresion'],r.get('componente',''),r.get('tipo',''))))

def encoded(value):return (json.dumps(validate(value),ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()
def load(root):
    p=Path(root)/FILE
    return validate(json.loads(p.read_bytes()) if p.exists() else EMPTY)

def proposed(current, rules, expected):
    if digest(current)!=expected:raise ValueError('El diccionario cambió en otra computadora. Recargá antes de guardar.')
    return validate(dict(version=1,revision=current['revision']+1,reglas=rules))

def compile_rules(value):
    enabled=[r for r in validate(value)['reglas'] if r['habilitada'] and r.get('categoria')!='otras']
    rows=sorted((r for r in enabled if r.get('tipo') not in ('descriptor','ortografia')),key=lambda r:-len(r['expresion']))
    return rows, re.compile('|'.join(r'\b(?P<custom'+str(i)+'>'+re.escape(r['expresion'])+r')\b' for i,r in enumerate(rows))) if rows else None, [dict(r,expresion=term) for r in enabled if r.get('tipo')=='descriptor' for term in terms(r)], [r for r in enabled if r.get('tipo')=='ortografia']
