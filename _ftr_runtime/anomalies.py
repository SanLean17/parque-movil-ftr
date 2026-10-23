"""Expresiones técnicas FTR: componente y descriptores contiguos, sin gravedad.

Los tokens conservan el texto original. Nunca se corrige la observación ni se
usa ESTADO para decidir componente, defecto o ubicación.
"""
import re
import unicodedata
from collections import Counter
from .mechanical_dictionary import VERSION, CATEGORIES, RULES, ALIASES, CODE_TOKEN
from .dictionary_rules import general, effective

PATTERN = re.compile('|'.join(r'\b(?P<rule'+str(i)+'>'+p+r')\b' for i, (_, p) in enumerate(RULES)))
OWNER = {c:k for k, values in CATEGORIES.items() for c in values}
CODE = re.compile(CODE_TOKEN)
NEUTRAL = re.compile(r'^(?:sin\s+(?:novedad(?:es)?|anomalias?|fallas?|defectos?|observaciones?)|ok|s/?n|ningun[oa]?|[-.]+)$')
NEGATION = re.compile(r'\b(?:sin\s+(?:fallas?|defectos?|anomalias?|problemas?|novedad(?:es)?|juego|perdidas?)|no\s+(?:presentan?|tienen?|hay|se\s+(?:detectan?|observan?))|en\s+buen\s+estado|funciona\s+(?:bien|correctamente)|ok)\b')
UNCERTAIN = re.compile(r'\b(?:posible|posiblemente|quizas?|duda|revisar|verificar|descartar|podria)\b|\?')
DEFECT = re.compile(r'\b(?:juego|rot[oa]s?|rotura|floj[oa]s?|suelt[oa]s?|fallas?|defectuos[oa]s?|desgaste|perdidas?|danad[oa]s?|cortad[oa]s?|pinchad[oa]s?|no\s+(?:funciona|anda))\b')
LOCATION_WORD = r'(?:delanter[oa]s?|traser[oa]s?|derech[oa]s?|izquierd[oa]s?|intern[oa]s?|extern[oa]s?|superior(?:es)?|inferior(?:es)?|der|izq|isk|del|tras|sup)'
POSITION = re.compile(r'\b'+LOCATION_WORD+r'\b')
LOCATION = r'(?:(?:zona|lado)\s+)?(?:media|'+LOCATION_WORD+r')'
GLUE = r'(?:sin|esta|estan|y|e|de|la|el|los|las|en|con|un|una|por|al|se|su|sus|tiene|presenta)'
BASE_DESCRIPTION = (r'no\s+(?:funciona|anda)|mal\s+estado|rot[oa]s?|rotura|floj[oa]s?|suelt[oa]s?|'
    r'juego|excesiv[oa]|fallas?|defectuos[oa]s?|desgaste|danad[oa]s?|cortad[oa]s?|pinchad[oa]s?|'
    r'desgastad[oa]s?|desinflad[oa]s?|reventad[oa]s?|perdidas?(?!\s+(?:de\s+)?aire\b)')
PNEUMATIC = {'pulmon_freno','pulmon_suspension','tanque_aire','valvula_descarga','valvula_niveladora',
    'flexibles_freno','freno_sin_ubicacion','freno_servicio','freno_estacionamiento','freno_emergencia',
    'neumatico_sin_ubicacion'}


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD',str(value or '').lower()) if not unicodedata.combining(c))


def canonical(location):
    names={'der':'derecho','izq':'izquierdo','isk':'izquierdo','del':'delantero','tras':'trasero','sup':'superior','superiores':'superior','inferiores':'inferior'}
    words=[]
    for word in location.split():
        for stem in ('delanter','traser','derech','izquierd','intern','extern'):
            word=re.sub('^'+stem+r'[oa]s?$',stem+'o',word)
        words.append(names.get(word,word))
    order={'delantero':0,'trasero':0,'derecho':1,'izquierdo':1,'superior':2,'inferior':2}
    return ' '.join(sorted(dict.fromkeys(words),key=lambda w:order.get(w,3))).replace('lado ','')


def clause_spans(original):
    # Proteger también códigos no confirmados: nunca reconocer un prefijo suyo.
    protected=[m.span() for m in re.finditer(CODE_TOKEN,original,re.I)]
    protected += [m.span() for m in re.finditer(r'\b(?:der|izq|isk|del|tras|sup)\.',original,re.I)]
    masked=list(original)
    for left,right in protected:masked[left:right]='_'*(right-left)
    # No confundir el número de "PF 3. A2" con una numeración de lista:
    # se protege PF 3, pero el punto posterior sigue separando expresiones.
    bounds=[m.span() for m in re.finditer(r'(?:^|(?<=\s))\d+[.)][ \t]*|[,;.\n\r!]+|[-–—]+',''.join(masked))]
    start=0
    for left,right in bounds+[(len(original),len(original))]:
        raw=original[start:left]
        if raw.strip():yield start+len(raw)-len(raw.lstrip()),left-(len(raw)-len(raw.rstrip()))
        start=right


def clauses(original):
    for start,end in clause_spans(original):yield original[start:end]


def descriptor_pattern(component, contextual=()):
    specific=''
    if component in ('barra_corta','barra_larga'):
        specific=r'|lado\s+(?:pit+t?man|eje|rueda)|enter[oa]s?'
    elif component=='tensores':
        specific=r'|mono|monio|posicionamiento(?:\s+del\s+eje)?'
    if component in PNEUMATIC:specific+=r'|perdidas?\s+(?:de\s+)?aire(?:\s+en\s+(?:el\s+)?sistema(?:\s+de)?)?'
    specific+=''.join('|'+re.escape(r['expresion']) for r in effective(contextual,component))
    return re.compile(r'\b(?:'+BASE_DESCRIPTION+'|'+LOCATION+specific+'|'+GLUE+r')\b')


def descriptors(text, component, reverse=False, contextual=(), blocked=()):
    """Solo la cadena contigua al componente. Lo desconocido corta el alcance."""
    tokens=list(descriptor_pattern(component,contextual).finditer(text));selected=[]
    cursor=len(text) if reverse else 0
    for token in reversed(tokens) if reverse else tokens:
        gap=text[token.end():cursor] if reverse else text[cursor:token.start()]
        if gap.strip(' \t.:()'+(',' if any(general(r) for r in contextual) else '')) or any(token.start()<b and token.end()>a for a,b in blocked):break
        selected.append(token)
        cursor=token.start() if reverse else token.end()
    return sorted(selected,key=lambda m:m.start())


def locations(text):
    result=[];axis=''
    for match in POSITION.finditer(text):
        word=canonical(match.group())
        if word in ('delantero','trasero'):
            axis=word
            if result and not result[-1].startswith(('delantero','trasero')):
                result[-1]=word+' '+result[-1]
            elif result and result[-1].startswith(word):continue
            else:result.append(word)
        elif word in ('derecho','izquierdo') and axis:
            if result and result[-1].startswith(axis) and not re.search(r'\b(?:derecho|izquierdo)\b',result[-1]):result[-1]+=' '+word
            else:result.append(axis+' '+word)
        elif word in ('superior','inferior','interno','externo') and result:result[-1]+=' '+word
        elif word in ('derecho','izquierdo') and result and result[-1] in ('superior','inferior'):result[-1]+=' '+word
        else:result.append(word)
    return result or ['sin_ubicacion']


def location_descriptors(text, tokens, prefix=False, component=None, contextual=()):
    result=[]
    for token in tokens:
        # La ubicación del moño es la del extremo del tensor; no identifica
        # otro tensor ni permite deducir el eje donde está montado.
        if component=='tensores' and token.group() in ('mono','monio'):break
        meaning=next((r['significado'] for r in effective(contextual,component) if r['expresion']==token.group()),token.group())
        if not re.fullmatch(LOCATION,meaning):continue
        # DEL también es una preposición. No convertir "del motor" en
        # delantero, ni "juego del amortiguador" en una ubicación.
        if token.group()=='del':
            rest=text[token.end():].strip(' .:()')
            if prefix or rest and not re.match(r'(?:'+LOCATION_WORD+'|'+BASE_DESCRIPTION+r')\b',rest):continue
        result.append(meaning)
    return ' '.join(result)


def component_of(match, custom_rows):
    return custom_rows[int(match.lastgroup[6:])]['componente'] if match.lastgroup.startswith('custom') else RULES[int(match.lastgroup[4:])][0]


def interpretation_spans(original,custom=None):
    """Una coma solo continúa un descriptor completo de un único componente."""
    contextual=custom[2] if custom and len(custom)>2 else ()
    spans=list(clause_spans(original))
    if not any(general(r) for r in contextual):return spans
    specific=(*custom[:2],[r for r in contextual if not general(r)])
    result=[]
    for index,(start,end) in enumerate(spans):
        if result and re.fullmatch(r'\s*,\s*',original[result[-1][1]:start]):
            left,right=result[-1];tail=fold(original[start:end])
            if index+1<len(spans):
                next_start,next_end=spans[index+1]
                following=fold(original[next_start:next_end])
                if re.fullmatch(r'\s*,\s*',original[end:next_start]) and (PATTERN.search(following) or custom[1] and custom[1].search(following)):result.append((start,end));continue
            before=analyze(original[left:right],specific)
            components={f['componente'] for f in before['hallazgos']}
            if len(before['hallazgos'])==1 and not before['pendientes'] and not (NEGATION.search(tail) or UNCERTAIN.search(tail) or re.search(r'\b(?:y|e)\b',tail)):
                component=next(iter(components));tokens=descriptors(tail,component,contextual=contextual)
                if tokens and tokens[-1].end()==len(tail) and any(general(r) and re.search(r'\b'+re.escape(r['expresion'])+r'\b',tail) for r in contextual):
                    result[-1]=(left,end);continue
        result.append((start,end))
    return result


def general_owners(clause,matches,custom_rows,contextual):
    """El descriptor entre dos componentes posibles no se consume por cercanía."""
    assignments=[]
    for word in {r['expresion'] for r in contextual if general(r)}:
        for token in re.finditer(r'\b'+re.escape(word)+r'\b',clause):
            if any(token.start()<m.end() and token.end()>m.start() for m in matches):continue
            candidates=[]
            left=[(i,m) for i,m in enumerate(matches) if m.end()<=token.start()]
            right=[(i,m) for i,m in enumerate(matches) if m.start()>=token.end()]
            for i,match in left[-1:]+right[:1]:
                gap=clause[match.end():token.start()] if match.end()<=token.start() else clause[token.end():match.start()]
                component=component_of(match,custom_rows)
                # Una conjunción marca una asociación distinta, no un puente.
                if re.search(r'\b(?:y|e)\b',gap):continue
                residue=descriptor_pattern(component,contextual).sub('',gap)
                if not residue.strip(' \t.:(),'):candidates.append(i)
            assignments.append((token.start(),token.end(),candidates[0] if len(candidates)==1 else None,word))
    return assignments


def analyze(value, custom=None):
    custom_rows,custom_pattern=(custom or ([],None))[:2]
    contextual=custom[2] if custom and len(custom)>2 else ()
    original=unicodedata.normalize('NFC',str(value or '').strip())
    if not original or NEUTRAL.fullmatch(fold(original)):
        return dict(hallazgos=[],pendientes=[],descriptores=[])
    findings={};unknown=[];absorbed=[]
    for start,stop in interpretation_spans(original,custom):
        raw=original[start:stop]
        clause=fold(raw)
        if NEUTRAL.fullmatch(clause):continue
        # No propagar una confirmación a una lista negada o incierta.
        if NEGATION.search(clause) or UNCERTAIN.search(clause):
            unknown.append(raw);continue
        codes=list(CODE.finditer(clause))
        invalid=[m for m in codes if re.sub(r'[^a-z0-9]','',m.group()) not in ALIASES]
        matches=[m for m in PATTERN.finditer(clause) if not any(m.start()<b.end() and m.end()>b.start() for b in invalid)]
        if custom_pattern:
            matches.extend(m for m in custom_pattern.finditer(clause) if not any(m.start()<b.end() and m.end()>b.start() for b in matches+invalid))
            matches.sort(key=lambda m:m.start())
        # Un sistema explícito incompatible no autoriza dos hallazgos:
        # "PS1 de freno" o "tensor sup de dirección" quedan para revisión.
        contradictory=set()
        generic={'direccion_sin_componente','suspension_sin_componente','transmision_sin_componente','electrico_sin_componente','freno_sin_ubicacion'}
        for left,right in zip(matches,matches[1:]):
            a,b=component_of(left,custom_rows),component_of(right,custom_rows)
            gap=clause[left.end():right.start()].strip()
            associated=not gap or bool(re.fullmatch(r'(?:(?:'+LOCATION_WORD+r')\s+)*(?:de|del)',gap))
            if a in ('tensores','pulmon_freno','pulmon_suspension','flexibles_freno','rotulas_direccion') and b in generic and OWNER[a]!=OWNER[b] and associated:
                contradictory.update((left,right))
        matches=[m for m in matches if m not in contradictory]
        # Pitman como extremo de una barra no es otra anomalía del brazo.
        matches=[m for i,m in enumerate(matches) if not (i and component_of(m,custom_rows)=='brazo_pitman'
            and component_of(matches[i-1],custom_rows) in ('barra_corta','barra_larga')
            and re.fullmatch(r'\s+lado\s+',clause[matches[i-1].end():m.start()]))]
        owners=general_owners(clause,matches,custom_rows,contextual)
        recognized=None
        if any(general(r) for r in contextual):
            baseline=analyze(raw,(custom_rows,custom_pattern,[r for r in contextual if not general(r)]))
            recognized={f['componente'] for f in baseline['hallazgos']}
        remainder=list(raw)
        for i,match in enumerate(matches):
            component=component_of(match,custom_rows)
            end=matches[i+1].start() if i+1<len(matches) else len(clause)
            prefix_start=matches[i-1].end() if i else 0
            prefix=clause[prefix_start:match.start()] if i==0 or any(owner==i and prefix_start<=a<b<=match.start() for a,b,owner,_ in owners) else ''
            suffix=clause[match.end():end]
            context=prefix+match.group()+suffix
            if component=='barra_corta' and match.group()=='corta' and prefix.strip():
                tokens=descriptors(prefix,component,reverse=True)
                if not tokens or prefix[:tokens[0].start()].strip():continue
            if component=='tensores' and re.search(r'\btensor(?:es)?\s+(?:de\s+)?direccion\b',clause):continue
            if match.lastgroup.startswith('custom'):
                explicit={k for k,p in (('direccion',r'\bdireccion\b'),('suspension',r'\bsuspension\b'),('transmision',r'\btransmision\b')) if re.search(p,clause)}
                if len(explicit)>1 or explicit and OWNER[component] not in explicit:continue
            if component in ('pulmon_freno','pulmon_suspension','freno_sin_ubicacion','suspension_sin_componente') and re.search(r'\bpulmon(?:es)?\s+(?:de\s+)?(?:frenos?\s+(?:de\s+)?suspension|suspension\s+(?:de\s+)?frenos?)\b',clause):continue
            if component=='flexibles_freno' and (re.search(r'\b(?:motor|combustible|agua|hidraulic[oa]|aceite|escape|suspension)\b',context) or re.search(r'flexibles?\s+(?:de\s+)?suspension',clause)):continue
            if component=='rotulas_direccion' and (re.search(r'\b(?:suspension|cadera|rodilla)\b',context) or re.search(r'rotulas?\s+(?:de\s+)?suspension',clause)):continue
            if component=='neumatico_sin_ubicacion' and match.group().startswith('cubierta') and not re.search(r'\b(?:delanter[oa]|traser[oa]|rueda|neumatico|pinchad[oa]|cortad[oa]|desgastad[oa])\b',context):continue
            local_contextual=[r for r in contextual if not general(r) or component in recognized] if recognized is not None else contextual
            selected_rules=effective(local_contextual,component)
            blocked=[(a,b) for a,b,owner,word in owners if owner!=i and not any(r['expresion']==word and not general(r) for r in selected_rules)]
            before=descriptors(prefix,component,reverse=True,contextual=local_contextual,blocked=[(a-prefix_start,b-prefix_start) for a,b in blocked])
            after=descriptors(suffix,component,contextual=local_contextual,blocked=[(a-match.end(),b-match.end()) for a,b in blocked])
            attached=' '.join(t.group() for t in before)+' '+match.group()+' '+' '.join(t.group() for t in after)
            for rule in selected_rules:
                attached=re.sub(r'\b'+re.escape(rule['expresion'])+r'\b',rule['significado'],attached)
            # DEL dentro de "pulmón del freno" es una preposición. Solo las
            # posiciones explícitas completas pueden venir dentro del nombre.
            internal=' '.join(p.group() for p in POSITION.finditer(match.group()) if len(p.group())>3)
            selected_locations=locations(location_descriptors(prefix,before,True,component,local_contextual)+' '+internal+' '+location_descriptors(suffix,after,component=component,contextual=local_contextual))
            if component in ('direccion_sin_componente','suspension_sin_componente','transmision_sin_componente','electrico_sin_componente') and not DEFECT.search(attached):
                # "dirección del domicilio" no usa DEL como ubicación técnica.
                if suffix[(after[-1].end() if after else 0):].strip(' .:()'):continue
            code=next((m for m in codes if m.start()>=match.start() and m.end()<=match.end()),None)
            reference=re.sub(r'[^a-z0-9]','',code.group()) if code else None
            if reference:
                target,location=ALIASES[reference]
                if component!='bujes':component=target
                if location!='sin_ubicacion' and any(('delanter' in p and 'trasero' in location) or ('traser' in p and 'delantero' in location) or ('derech' in p and 'izquierdo' in location) or ('izquierd' in p and 'derecho' in location) for p in selected_locations):continue
                selected_locations=[location] if location!='sin_ubicacion' else selected_locations
            if component in ('direccion_sin_componente','suspension_sin_componente','transmision_sin_componente','electrico_sin_componente') and selected_locations==['sin_ubicacion'] and not DEFECT.search(attached):continue
            # Las estadísticas de barras no separan extremos.
            if component in ('barra_corta','barra_larga'):selected_locations=['sin_ubicacion']
            if component=='freno_sin_ubicacion' and re.search(r'perdidas?\s+(?:de\s+)?aire',attached):selected_locations=['sin_ubicacion']
            for location in selected_locations:
                selected=component
                if component in ('freno_sin_ubicacion','neumatico_sin_ubicacion'):
                    if location.startswith('delanter'):selected='frenos_delanteros' if component.startswith('freno') else 'neumaticos_delanteros'
                    elif location.startswith('traser'):selected='frenos_traseros' if component.startswith('freno') else 'neumaticos_traseros'
                # A7/A8 son referencias distintas, sin inventarles una posición.
                key=(OWNER[selected],selected,canonical(location),reference if location=='sin_ubicacion' else None)
                defect='no_identificado'
                for label,pattern in (('corte',r'\bcortad[oa]s?\b'),('pinchadura',r'\bpinchad[oa]s?\b'),('rotura',r'\brot[oa]s?\b'),('flojo',r'\bfloj[oa]s?\b'),('suelto',r'\bsuelt[oa]s?\b'),('no_funciona',r'\bno\s+(?:funciona|anda)\b')):
                    if re.search(pattern,attached):defect=label;break
                findings.setdefault(key,dict(categoria=key[0],componente=key[1],ubicacion=key[2],referencia=reference,defecto=defect))
            remainder[match.start():match.end()]=' '*(match.end()-match.start())
            for offset,tokens in ((prefix_start,before),(match.end(),after)):
                for token in tokens:
                    left=offset+token.start();right=offset+token.end()
                    remainder[left:right]=' '*(right-left)
                    if not re.fullmatch(GLUE,token.group()):absorbed.append(dict(componente=component,texto=raw[left:right]))
        rest=re.sub(r'^[\s,:./()\-]+|[\s,:./()\-]+$','', ''.join(remainder))
        rest=re.sub(r'\s+',' ',rest).strip()
        if rest and rest.lower() not in ('y','e'):unknown.append(rest)
    result=dict(hallazgos=[findings[k] for k in sorted(findings,key=lambda k:tuple(x or '' for x in k))],
        pendientes=list(dict.fromkeys(unknown)),descriptores=absorbed)
    if any(general(r) for r in contextual):
        baseline=analyze(original,(custom_rows,custom_pattern,[r for r in contextual if not general(r)]))
        # Un descriptor general no demuestra que dos posiciones sean dos piezas.
        # Si altera la cantidad de componentes ya reconocidos, conservarlos y
        # mantener la interpretación pendiente, sin inflar ni reducir el total.
        counts=lambda value:Counter(f['componente'] for f in value['hallazgos'])
        if counts(result)!=counts(baseline):
            baseline['pendientes']=list(dict.fromkeys(baseline['pendientes']+result['pendientes']))
            return baseline
    return result


def classify(value):
    result=analyze(value)
    return [(r['categoria'],r['componente'],r['ubicacion']) for r in result['hallazgos']], result['pendientes']
