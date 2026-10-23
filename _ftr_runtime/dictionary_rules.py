"""Equivalencias confirmadas: datos literales, sin regex ni observaciones privadas."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from .mechanical_dictionary import CATEGORIES

FILE = '_ftr_diccionario.json'
EMPTY = {'version': 1, 'revision': 1, 'reglas': []}
GENERAL = {'falla','fallas','juego','roto','rota','flojo','floja','sin','no','si','ok','mal','bien','estado','novedad','novedades','otro','otros','unidad','vehiculo','coche','interno','dominio','fecha','linea','izquierdo','derecho','delantero','trasero','perdida','aire','aceite'}

def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD',value.lower().strip()) if not unicodedata.combining(c))

def expression(value):
    # Solo abreviaturas/términos técnicos cortos. Nunca frases de inspectores,
    # patentes, fechas, identificadores, puntuación ni sintaxis ejecutable.
    if not isinstance(value,str):raise ValueError('Ingresá una abreviatura técnica general.')
    value=normalized(value)
    if not re.fullmatch(r'(?:[a-z]{2,24}|[a-z]{1,4}[0-9]{1,2})',value) or value in GENERAL:
        raise ValueError('Usá un término técnico breve o abreviatura, sin frases, datos individuales ni símbolos.')
    if re.fullmatch(r'[ra][0-9]+|pf',value):raise ValueError('Los códigos R, A y PF pertenecen al diccionario confirmado original.')
    return value

def validate(value):
    if not isinstance(value,dict) or set(value)!={'version','revision','reglas'} or value['version']!=1 or type(value['revision']) is not int or value['revision']<1 or not isinstance(value['reglas'],list) or len(value['reglas'])>300:
        raise ValueError('Diccionario no válido.')
    from .anomalies import PATTERN, NEUTRAL
    rows=[];seen=set()
    for row in value['reglas']:
        if not isinstance(row,dict) or set(row)!={'expresion','categoria','componente','habilitada'}:raise ValueError('Regla no válida.')
        word=expression(row['expresion'])
        if word in seen:raise ValueError('Expresión duplicada o en conflicto; modificá la regla existente.')
        if PATTERN.search(word) or NEUTRAL.fullmatch(word):raise ValueError('La expresión ya está definida por las reglas originales.')
        if row['categoria'] not in CATEGORIES or row['componente'] not in CATEGORIES[row['categoria']] or type(row['habilitada']) is not bool:
            raise ValueError('La categoría y el componente no coinciden.')
        seen.add(word);rows.append(dict(row,expresion=word))
    return dict(version=1,revision=value['revision'],reglas=sorted(rows,key=lambda r:r['expresion']))

def encoded(value):return (json.dumps(validate(value),ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()
def load(root):
    p=Path(root)/FILE
    return validate(json.loads(p.read_bytes()) if p.exists() else EMPTY)

def proposed(current, rules, expected):
    if digest(current)!=expected:raise ValueError('El diccionario cambió en otra computadora. Recargá antes de guardar.')
    return validate(dict(version=1,revision=current['revision']+1,reglas=rules))

def compile_rules(value):
    rows=[r for r in validate(value)['reglas'] if r['habilitada'] and r['categoria']!='otras']
    return rows, re.compile('|'.join(r'\b(?P<custom'+str(i)+'>'+re.escape(r['expresion'])+r')\b' for i,r in enumerate(rows))) if rows else None
