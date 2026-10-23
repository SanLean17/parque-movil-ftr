"""Motor conservador de menciones técnicas. No interpreta ESTADO ni gravedad."""
import re
import unicodedata
from .mechanical_dictionary import VERSION, CATEGORIES, RULES, ALIASES

PATTERN = re.compile('|'.join(r'\b(?P<rule'+str(i)+'>'+p+r')\b' for i, (_, p) in enumerate(RULES)))
OWNER = {c:k for k, values in CATEGORIES.items() for c in values}
POSITION = re.compile(r'\b(?:delanter[oa]s?|traser[oa]s?)(?:\s+(?:lado\s+)?(?:derech[oa]s?|izquierd[oa]s?))?\b|\b(?:derech[oa]s?|izquierd[oa]s?)\b')
NEUTRAL = re.compile(r'^(?:sin\s+(?:novedad(?:es)?|anomalias?|fallas?|defectos?|observaciones?)|ok|s/?n|ningun[oa]?|[-.]+)$')
NEGATION = re.compile(r'\b(?:sin\s+(?:fallas?|defectos?|anomalias?|problemas?|novedad(?:es)?|juego|perdidas?)|no\s+(?:presenta|tiene|se\s+(?:detecta|observa))|en\s+buen\s+estado|funciona\s+(?:bien|correctamente)|ok)\b')
UNCERTAIN = re.compile(r'\b(?:posible|posiblemente|quizas?|duda|revisar|verificar|descartar|podria)\b|\?')
DEFECT = re.compile(r'\b(?:juego|rot[oa]s?|rotura|flojos?|flojas?|fallas?|defectuos[oa]s?|desgaste|perdidas?|danad[oa]s?|no\s+funciona)\b')
DESCRIPTORS = re.compile(r'\b(?:no\s+(?:funciona|anda)|mal\s+estado|sin|esta|estan|y|e|de|del|la|el|los|las|en|con|un|una|por|al|se|su|sus|lado|tiene|presenta|rot[oa]s?|rotura|flojos?|flojas?|juego|excesiv[oa]|fallas?|defectuos[oa]s?|desgaste|perdidas?|aceite|aire|danad[oa]s?|cortad[oa]s?|pinchad[oa]s?|desgastad[oa]s?|desinflad[oa]s?|reventad[oa]s?)\b')


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD',str(value or '').lower()) if not unicodedata.combining(c))


def canonical(location):
    for stem in ('delanter','traser','derech','izquierd'):
        location=re.sub(stem+r'[oa]s?',stem+'o',location)
    return location.replace('lado ','')


def analyze(value, custom=None):
    custom_rows,custom_pattern=custom or ([],None)
    original=unicodedata.normalize('NFC',str(value or '').strip())
    if not original or NEUTRAL.fullmatch(fold(original)):
        return dict(hallazgos=[],pendientes=[])
    # Se conservan caso y acentos para el informe cifrado.
    # Las conjunciones se consumen entre coincidencias, sin perder el alcance
    # de una negación: «no presenta falla de cardán y frenos» no confirma frenos.
    separator=r'[,;\n]+|(?:^|\s)\d+[.)]\s*'
    normalized=fold(original)
    bounds=[(m.start(),m.end()) for m in re.finditer(separator,normalized)]
    spans=[];start=0
    for left,right in bounds:spans.append((start,left));start=right
    spans.append((start,len(original)))
    findings={};unknown=[]
    for start,end in spans:
        raw=original[start:end].strip();clause=fold(raw)
        if not clause or NEUTRAL.fullmatch(clause):continue
        if NEGATION.search(clause) or UNCERTAIN.search(clause):
            unknown.append(raw)
            continue
        matches=list(PATTERN.finditer(clause))
        if custom_pattern:
            matches.extend(m for m in custom_pattern.finditer(clause) if not any(m.start()<b.end() and m.end()>b.start() for b in matches))
            matches.sort(key=lambda m:m.start())
        remainder=list(raw)
        for i, match in enumerate(matches):
            component=custom_rows[int(match.lastgroup[6:])]['componente'] if match.lastgroup.startswith('custom') else RULES[int(match.lastgroup[4:])][0]
            end=matches[i+1].start() if i+1<len(matches) else len(clause)
            prefix=clause[:match.start()] if i==0 else ''
            suffix=clause[match.end():end]
            context=prefix+match.group()+suffix
            if NEGATION.search(context) or UNCERTAIN.search(context):continue
            if component in ('pulmon_freno','pulmon_suspension','freno_sin_ubicacion','suspension_sin_componente') and re.search(r'\bpulmon(?:es)?\s+(?:de\s+)?(?:frenos?\s+(?:de\s+)?suspension|suspension\s+(?:de\s+)?frenos?)\b',clause):continue
            if component=='flexibles_freno' and (re.search(r'\b(?:motor|combustible|agua|hidraulico|aceite|escape|suspension)\b',context) or re.search(r'flexibles?\s+(?:de\s+)?suspension',clause)):continue
            if component=='pulmon_suspension' and re.search(r'\b(?:frenos?|pf)\b',clause) and 'suspension' not in match.group():continue
            if component=='rotulas_direccion' and (re.search(r'\b(?:suspension|cadera|rodilla)\b',context) or re.search(r'rotulas?\s+(?:de\s+)?suspension',clause)):continue
            if component=='neumatico_sin_ubicacion' and match.group().startswith('cubierta') and not re.search(r'\b(?:delanter[oa]|traser[oa]|rueda|neumatico|pinchad[oa]|cortad[oa]|desgastad[oa])\b',context):continue
            locations=[m.group() for m in POSITION.finditer(match.group()+' '+suffix)] or ['sin_ubicacion']
            alias=re.search(r'\b([ra][1-8])\b',match.group())
            reference=alias.group() if alias and alias.group() in ALIASES else None
            if reference:
                target,location=ALIASES[reference]
                if component!='bujes':component=target
                if locations!=['sin_ubicacion'] and any(('delanter' in p and 'trasero' in location) or ('traser' in p and 'delantero' in location) or ('derech' in p and 'izquierdo' in location) or ('izquierd' in p and 'derecho' in location) for p in locations):continue
                locations=[location]
            if component in ('direccion_sin_componente','suspension_sin_componente','transmision_sin_componente','electrico_sin_componente') and locations==['sin_ubicacion'] and not DEFECT.search(context):continue
            axis=''
            for location in locations:
                if location.startswith(('delanter','traser')):axis=location.split()[0]
                elif axis and location.startswith(('derech','izquierd')):location=axis+' '+location
                selected=component
                if component in ('freno_sin_ubicacion','neumatico_sin_ubicacion'):
                    if location.startswith('delanter'):selected='frenos_delanteros' if component.startswith('freno') else 'neumaticos_delanteros'
                    elif location.startswith('traser'):selected='frenos_traseros' if component.startswith('freno') else 'neumaticos_traseros'
                key=(OWNER[selected],selected,canonical(location))
                # R3 juego conserva la referencia sin inventar su defecto.
                defect='no_identificado'
                for label,pattern in (('corte',r'\bcortad[oa]s?\b'),('pinchadura',r'\bpinchad[oa]s?\b'),('rotura',r'\brot[oa]s?\b'),('flojo',r'\bfloj[oa]s?\b'),('no_funciona',r'\bno funciona\b')):
                    if re.search(pattern,context):defect=label;break
                findings.setdefault(key,dict(categoria=key[0],componente=key[1],ubicacion=key[2],referencia=reference,defecto=defect))
            remainder[match.start():match.end()]=' '*(match.end()-match.start())
            for token in list(POSITION.finditer(clause[match.end():end]))+list(DESCRIPTORS.finditer(clause[match.end():end])):
                left=match.end()+token.start();right=match.end()+token.end();remainder[left:right]=' '*(right-left)
            if i==0:
                for token in DESCRIPTORS.finditer(prefix):remainder[token.start():token.end()]=' '*(token.end()-token.start())
        rest=re.sub(r'^[\s:./()\-]+|[\s:./()\-]+$','', ''.join(remainder))
        rest=re.sub(r'\s+',' ',rest).strip()
        if rest and rest.lower() not in ('y','e'):unknown.append(rest)
    return dict(hallazgos=[findings[k] for k in sorted(findings)],pendientes=list(dict.fromkeys(unknown)))


def classify(value):
    result=analyze(value)
    return [(r['categoria'],r['componente'],r['ubicacion']) for r in result['hallazgos']], result['pendientes']
