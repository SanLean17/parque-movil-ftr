"""Equivalencias ortográficas confirmadas; no modifica la fuente original."""
import re
import unicodedata

BASE=(('barta','barra'),('buge','buje'),('suleto','suelto'),('monio','moño'),('isk','izquierdo'))

def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower()) if not unicodedata.combining(c))

def transform(text,extra=()):
    original=text
    positions=[(i,i+1) for i in range(len(text))]
    def replace(pattern,target,group=0):
        nonlocal text,positions
        for m in reversed(list(re.finditer(pattern,text,flags=re.I))):
            start,end=m.span(group)
            span=(positions[start][0],positions[end-1][1])
            text=text[:start]+target+text[end:]
            positions[start:end]=[span]*len(target)
    def confirmed():
        for source,target in BASE:replace(r'\b'+source+r'\b',target)
        replace(r'\bamor(?=[ \t]+(?:de[ \t]+)?direcci[oó]n\b)','amortiguador')
        replace(r'\bbuje[ \t]+de[ \t]+(amortiguar)\b','amortiguador',1)
        replace(r'\btensor[ \t]+(sub)\b','superior',1)
    confirmed()
    for row in extra:
        replace(r'\b'+r'[ \t]+'.join(re.escape(w) for w in row['expresion'].split())+r'\b',row['corregida'])
    # A validated target goes through the same base interpretation when applied.
    # Only one custom pass: no recursive rules, no cross-anomaly whitespace.
    confirmed()
    def original_pending(start,end):
        # Cada carácter conserva su intervalo fuente, incluso si la corrección
        # cambia la longitud o aparece junto a la misma palabra bien escrita.
        return original[positions[start][0]:positions[end-1][1]] if end>start else ''
    return text,original_pending

def validate(row):
    if set(row)!={'tipo','expresion','corregida','habilitada'} or row['tipo']!='ortografia' or type(row['habilitada']) is not bool:raise ValueError('Corrección ortográfica no válida.')
    terms=[]
    for key in ('expresion','corregida'):
        value=row[key]
        if not isinstance(value,str) or not re.fullmatch(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ ]{2,64}',value):raise ValueError('Usá palabras, sin números, datos personales ni símbolos.')
        value=' '.join(normalize(value).split())
        if not 1<=len(value.split())<=5:raise ValueError('Usá de una a cinco palabras.')
        terms.append(value)
    source,target=terms
    if source==target:raise ValueError('La expresión original y la corregida deben ser diferentes.')
    from .dictionary_rules import TECHNICAL,DESCRIPTORS,GENERAL
    from .anomalies import analyze
    known=TECHNICAL|DESCRIPTORS|{'barra','amortiguador','buge','buje','mono','superior','inferior','diferencial'}
    if not all(w in known for w in target.split()):
        result=analyze(target)
        if not result['hallazgos'] or result['pendientes']:raise ValueError('La expresión corregida debe tener un significado técnico reconocido.')
    if source in GENERAL or source in ('kit','sube') or target in ('kit','sube'):raise ValueError('No se pueden sustituir términos genéricos ni incidencias KIT mediante una corrección.')
    # Un error nuevo no tiene por qué pertenecer al vocabulario, pero debe estar
    # próximo a la escritura confirmada. Así no se publican observaciones libres.
    def distance(a,b):
        row=list(range(len(b)+1))
        for i,x in enumerate(a,1):
            new=[i]
            for j,y in enumerate(b,1):new.append(min(new[-1]+1,row[j]+1,row[j-1]+(x!=y)))
            row=new
        return row[-1]
    if distance(source,target)>max(2,len(target)//3):raise ValueError('La diferencia excede una corrección ortográfica. Usá la clasificación de componentes o una interpretación particular.')
    return dict(tipo='ortografia',expresion=source,corregida=target,habilitada=row['habilitada'])
