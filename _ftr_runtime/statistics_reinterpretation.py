"""Revisión explícita desde informes completos: sin red ni cambios de fuentes.

Extiende la revisión histórica protegida existente con las mismas barreras:
archivo anterior, diccionario, registros y resultado deben coincidir con la
vista previa confirmada. Prepara el conjunto en un área aislada antes de copiar.
"""
import copy
import hashlib
import json
import shutil
import tempfile
from datetime import datetime,timezone
from pathlib import Path
from . import mechanical_review as review,public_statistics as stats,statistics_archive as archive,dictionary_rules as rules
from .config import load as config_load
from .kit_sube import aggregate

def digest(raw):return hashlib.sha256(raw).hexdigest()

def prepare(root,capsule):
    root=Path(root);archive.validate_collection(root)
    events,previous,_,_=review.unpack(capsule)
    year=previous['periodo'];raw=(root/f'estadisticas/{year}.json').read_bytes()
    published=stats.validate(json.loads(raw))
    if published!=previous:raise ValueError('El informe no corresponde al archivo publicado actual. No se recalcula una lectura distinta.')
    dictionary=rules.load(root);updated=copy.deepcopy(published)
    updated.update(version=4,anomalias=stats.mechanics(events,dictionary=dictionary)[0],
        kit_sube=aggregate(events,published['lineas']),interpretacion=dict(revision=dictionary['revision'],sha256=rules.digest(dictionary)))
    stats.validate(updated);review.unchanged_controls(published,updated)
    confirmation=dict(periodo=year,expected_archive=digest(raw),expected_dictionary=rules.digest(dictionary),
        expected_records=capsule['huella_registros'],expected_result=review.fingerprint(updated))
    return dict(confirmation=confirmation,antes=published,despues=updated)

def apply(root,capsule,confirmation):
    root=Path(root);proposal=prepare(root,capsule)
    if proposal['confirmation']!=confirmation:raise ValueError('La vista previa cambió. Revisá y confirmá nuevamente; no se publicó.')
    updated=proposal['despues'];year=updated['periodo'];cfg=config_load(root)
    if year>cfg['period']:raise ValueError('No se activa un período futuro mediante una revisión.')
    if json.loads((root/stats.FILE).read_bytes())['periodo']!=cfg['period']:raise ValueError('El período activo no coincide con la configuración.')
    old=(root/f'estadisticas/{year}.json').read_bytes();body=archive.encoded(updated)
    prior=f'estadisticas/revisiones/{year}/{digest(old)}.json'
    evidence=f'estadisticas/revisiones/{year}/{digest(body)}-revision.json'
    with tempfile.TemporaryDirectory(prefix='ftr-reinterpretacion-') as tmp:
        stage=Path(tmp);shutil.copytree(root/'estadisticas',stage/'estadisticas');shutil.copyfile(root/stats.FILE,stage/stats.FILE)
        index=archive.validate_collection(stage)
        (stage/prior).parent.mkdir(parents=True,exist_ok=True)
        if (stage/prior).exists() and (stage/prior).read_bytes()!=old:raise ValueError('El respaldo existente no coincide.')
        (stage/prior).write_bytes(old)
        (stage/evidence).write_bytes(archive.encoded(dict(version=1,periodo=year,anterior=digest(old),nuevo=digest(body),
            diccionario=updated['interpretacion'],motor_revision=updated['anomalias']['motor_revision'],
            huella_registros=capsule['huella_registros'],recalculo_utc=datetime.now(timezone.utc).isoformat(),
            origen='informe_protegido_completo',confirmacion=confirmation)))
        target=f'estadisticas/{year}.json';(stage/target).write_bytes(body)
        index['periodos']=[archive.entry(updated,body) if x['periodo']==year else x for x in index['periodos']]
        (stage/stats.INDEX).write_bytes(archive.encoded(index))
        paths=[target,stats.INDEX,prior,evidence]
        if year==cfg['period']:(stage/stats.FILE).write_bytes(body);paths.append(stats.FILE)
        archive.validate_collection(stage)
        manifest=json.loads((root/'ftr_publicacion.json').read_bytes())
        for name in paths:manifest['files_sha256'][name]=digest((stage/name).read_bytes())
        (stage/'ftr_publicacion.json').write_bytes(archive.encoded(manifest));paths.append('ftr_publicacion.json')
        # Git publica estos archivos juntos. Ninguna llamada a Drive/CNRT ni al
        # remitente de órdenes ocurre en este procedimiento explícito.
        for name in paths:
            (root/name).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(stage/name,root/name)
    return paths
