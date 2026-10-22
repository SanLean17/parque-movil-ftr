"""Archivo anual público. Solo agregados; conserva bytes de períodos anteriores."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from .public_statistics import FILE, INDEX, validate


def encoded(data):
    return (json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')


def entry(data, content):
    return dict(periodo=data['periodo'],archivo=f"estadisticas/{data['periodo']}.json",
        version=data['version'],version_reglas=data['anomalias']['version_reglas'],
        lectura_planilla_utc=data['lectura_planilla_utc'],lineas=[r['linea'] for r in data['lineas']],
        sha256=hashlib.sha256(content).hexdigest())


def validate_index(index):
    if not isinstance(index,dict) or set(index)!= {'version','periodos'} or type(index['version']) is not int or index['version']!=1 or not isinstance(index['periodos'],list) or not index['periodos']:
        raise ValueError('Índice de períodos estadísticos inválido.')
    years=[]
    for item in index['periodos']:
        if not isinstance(item,dict) or set(item)!= {'periodo','archivo','version','version_reglas','lectura_planilla_utc','lineas','sha256'}:
            raise ValueError('Metadatos de período inválidos.')
        year=item['periodo'];years.append(year)
        if type(year) is not int or not 2000<=year<=2100 or item['archivo']!=f'estadisticas/{year}.json' or item['version'] not in (1,2) or item['version_reglas'] not in (1,2):
            raise ValueError('Versión o ruta histórica no admitida.')
        if not re.fullmatch('[a-f0-9]{64}',item['sha256']) or datetime.fromisoformat(item['lectura_planilla_utc']).tzinfo is None:
            raise ValueError('Integridad histórica no verificable.')
        if not isinstance(item['lineas'],list) or any(type(n) is not int or n<=0 for n in item['lineas']) or item['lineas']!=sorted(set(item['lineas'])):
            raise ValueError('Líneas históricas inválidas.')
    if years!=sorted(set(years),reverse=True):raise ValueError('Períodos duplicados o desordenados.')
    return index


def validate_collection(root, read=None):
    root=Path(root);read=read or (lambda path:(root/path).read_bytes())
    index=validate_index(json.loads(read(INDEX)))
    for item in index['periodos']:
        content=read(item['archivo']);data=validate(json.loads(content))
        if entry(data,content)!=item:raise ValueError('El histórico no coincide con su índice verificado.')
    current=read(FILE);data=validate(json.loads(current))
    if entry(data,current) not in index['periodos']:raise ValueError('La estadística activa no coincide con su archivo anual.')
    return index


def data_paths(root):
    index=validate_collection(root)
    return [FILE,INDEX,*[r['archivo'] for r in index['periodos']]]


def publish(root, data):
    """Preparar dentro del área temporal; Git publica el conjunto en un commit.

    Nunca se borra un año. Una revisión de un año anterior al último disponible
    requiere una operación futura explícita; no la hace el reloj automáticamente.
    """
    root=Path(root);validate(data);files={}
    if (root/INDEX).exists():
        index=validate_collection(root)
        files={item['periodo']:(root/item['archivo']).read_bytes() for item in index['periodos']}
        actual_paths={p.name for p in (root/'estadisticas').glob('*.json') if p.name!='indice.json'}
        if actual_paths!={f'{year}.json' for year in files}:raise ValueError('Existen períodos sin índice; no se descartan archivos.')
    elif (root/FILE).exists():
        content=(root/FILE).read_bytes();old=validate(json.loads(content));files[old['periodo']]=content
        if (root/'estadisticas').exists() and any((root/'estadisticas').glob('*.json')):
            raise ValueError('El archivo anual requiere un índice válido; se conserva sin cambios.')
    year=data['periodo']
    if files and year<max(files):raise ValueError('Un período anterior requiere una revisión histórica explícita; se conserva su última versión.')
    if year in files and datetime.fromisoformat(data['lectura_planilla_utc'])<datetime.fromisoformat(json.loads(files[year])['lectura_planilla_utc']):
        raise ValueError('Se rechazó una lectura anterior a la estadística guardada.')
    content=encoded(data);files[year]=content
    index=validate_index(dict(version=1,periodos=[entry(validate(json.loads(files[y])),files[y]) for y in sorted(files,reverse=True)]))
    writes={f'estadisticas/{y}.json':body for y,body in files.items()}
    writes[FILE]=content;writes[INDEX]=encoded(index)
    for path,body in writes.items():
        target=root/path
        if target.exists() and target.read_bytes()==body:continue
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_suffix('.json.tmp');temp.write_bytes(body);temp.replace(target)
