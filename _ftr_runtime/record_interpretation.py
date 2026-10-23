"""Interpretaciones privadas ligadas al registro y al texto exactos. Sin E/S."""
import copy
import re
from . import anomalies, dictionary_rules as rules
from .mechanical_review import fingerprint

LOCATIONS = ('sin_ubicacion','delantero','trasero','derecho','izquierdo','superior','inferior',
             'delantero derecho','delantero izquierdo','trasero derecho','trasero izquierdo',
             'trasero derecho interno','trasero izquierdo interno','superior derecho','superior izquierdo')
DEFECTS = ('no_identificado','corte','pinchadura','rotura','flojo','suelto','no_funciona','juego','desgaste')

def reference(event):
    import hashlib,json
    ref={k:event.get(k) for k in ('linea','pestana','pestana_posicion','fila','dominio','interno')}
    value=event['fecha'];day=value if isinstance(value,str) else value.isoformat()
    ref.update(periodo=int(day[:4]),fecha=day,novedades_original=event.get('novedades',''),
               estado_formal=event.get('estado_original',event.get('estado')))
    ref['registro_id']=hashlib.sha256(json.dumps([ref.get(k) for k in ('periodo','linea','fecha','dominio','interno','pestana','fila','novedades_original')],ensure_ascii=False).encode()).hexdigest()
    return ref

def suggestions(original,dictionary):
    result=[]
    # El texto se corta por sus posiciones originales, nunca se reescribe.
    for start,end in anomalies.clause_spans(original):
        result.append(dict(inicio=start,fin=end,modo='automatico',hallazgos=[]))
    return result

def validated(original,fragments):
    if not isinstance(fragments,list) or not 1<=len(fragments)<=100 or any(not isinstance(r,dict) or type(r.get('inicio')) is not int for r in fragments):raise ValueError('Revisá los fragmentos seleccionados.')
    result=[];end=0
    for row in sorted(fragments,key=lambda r:r.get('inicio',-1)):
        if not isinstance(row,dict) or set(row)!={'inicio','fin','modo','hallazgos'}:raise ValueError('Fragmento no válido.')
        a,b=row['inicio'],row['fin']
        if type(a) is not int or type(b) is not int or not end<=a<b<=len(original):raise ValueError('Los fragmentos deben conservar posiciones válidas, sin superponerse.')
        end=b
        if row['modo'] not in ('automatico','confirmado','pendiente') or not isinstance(row['hallazgos'],list) or len(row['hallazgos'])>20:raise ValueError('Interpretación no válida.')
        if row['modo']!='confirmado' and row['hallazgos'] or row['modo']=='confirmado' and not row['hallazgos']:raise ValueError('Elegí el componente o mantené el fragmento pendiente.')
        for finding in row['hallazgos']:
            if not isinstance(finding,dict) or set(finding)!={'categoria','componente','ubicacion','referencia','defecto'}:raise ValueError('Hallazgo no válido.')
            if finding['categoria']=='otras' or finding['categoria'] not in rules.CATEGORIES or finding['componente'] not in rules.CATEGORIES[finding['categoria']]:raise ValueError('Componente no válido.')
            position=finding['ubicacion']
            if position not in LOCATIONS and not re.fullmatch(r'trasero (?:[ar][3-8]|pf[3-6]|ps[34])',str(position)):raise ValueError('Ubicación no confirmada.')
            if finding['defecto'] not in DEFECTS:raise ValueError('Defecto no válido.')
            if finding['referencia'] is not None and (finding['referencia'] not in anomalies.ALIASES or finding['referencia'] not in re.sub(r'[^a-z0-9]','',anomalies.fold(original[a:b]))):raise ValueError('Referencia ajena al fragmento.')
        result.append(copy.deepcopy(row))
    return result

def interpret(original,fragments,dictionary):
    fragments=validated(original,fragments);compiled=rules.compile_rules(dictionary)
    findings={};pending=[];descriptors=[];cursor=0
    for row in fragments+[dict(inicio=len(original),fin=len(original),modo='pendiente',hallazgos=[])]:
        gap=original[cursor:row['inicio']].strip(' ,;.\n\r\t–—-')
        if gap:pending.append(gap)  # Borrar un fragmento no borra su observación.
        text=original[row['inicio']:row['fin']];cursor=row['fin']
        if not text:continue
        analysis=anomalies.analyze(text,compiled) if row['modo']=='automatico' else dict(hallazgos=row['hallazgos'],pendientes=[text] if row['modo']=='pendiente' else [],descriptores=[])
        for f in analysis['hallazgos']:
            key=(f['categoria'],f['componente'],anomalies.canonical(f['ubicacion']),f['referencia'] if f['ubicacion']=='sin_ubicacion' else None)
            findings.setdefault(key,f)
        pending.extend(analysis['pendientes']);descriptors.extend(analysis['descriptores'])
    return dict(hallazgos=[findings[k] for k in sorted(findings,key=lambda k:tuple(x or '' for x in k))],pendientes=list(dict.fromkeys(pending)),descriptores=descriptors)

def correction(event,fragments,rule=None,dictionary=None):
    event=dict(event,fecha=reference(event)['fecha'])
    result=dict(registro_id=reference(event)['registro_id'],huella=fingerprint(event),
                periodo=reference(event)['periodo'],fragmentos=validated(event.get('novedades',''),fragments))
    if rule is not None:
        result['regla']=rules.validate(dict(version=1,revision=1,reglas=[rule]))['reglas'][0]
    return result

def apply(event,corrections,dictionary):
    event=dict(event,fecha=reference(event)['fecha'])
    saved=corrections.get(reference(event)['registro_id'])
    # Cambiar fecha, estado, fila o texto invalida la decisión anterior.
    if saved and saved['huella']==fingerprint(event):
        if saved.get('regla'):
            rule=saved['regla']
            def overlaps(row):
                if row.get('tipo')==rule.get('tipo')=='descriptor' and row['componente']!=rule['componente']:return False
                return re.search(r'\b'+re.escape(row['expresion'])+r'\b',rule['expresion']) or re.search(r'\b'+re.escape(rule['expresion'])+r'\b',row['expresion'])
            rows=[r for r in dictionary['reglas'] if not overlaps(r)]+[rule]
            candidate=rules.validate(dict(dictionary,reglas=rows))
            return anomalies.analyze(event['novedades'],rules.compile_rules(candidate))
        return interpret(event['novedades'],saved['fragmentos'],dictionary)
    return anomalies.analyze(event.get('novedades',''),rules.compile_rules(dictionary))
