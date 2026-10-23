"""Órdenes explícitas de diccionario/importación. Separadas de la agenda de fuentes."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from _ftr_runtime import config, dictionary_rules as rules, historical_statistics as historical, statistics_commands as commands
from _ftr_runtime import mechanical_review as review, statistics_archive as archive, public_statistics as stats
from _ftr_runtime import worker
from _ftr_admin import diagnostico_administrativo as admin

def apply(root,action,payload,expected,export=None,report_dir=None):
    root=Path(root);cfg=config.load(root)
    if config.digest(cfg)!=expected:raise ValueError('Cambió la configuración activa. Revisá la orden antes de repetirla.')
    value=commands.clean(action,payload)
    dictionary=rules.load(root)
    if action=='dictionary-save':
        updated=rules.proposed(dictionary,value['reglas'],value['expected_dictionary'])
        (root/rules.FILE).write_bytes(rules.encoded(updated))
        return [rules.FILE]
    year=value['period'];source=admin.base.spreadsheet_id(value['sheetUrl'])
    if year>=cfg['period'] or source==admin.base.spreadsheet_id(cfg['sheetUrl']):raise ValueError('Usá una fuente independiente de un período anterior al activo.')
    previous=None
    if action=='history-import':
        if (root/f'estadisticas/{year}.json').exists():raise ValueError('El año ya está archivado. No se vuelve a descargar ni sobrescribir.')
    else:
        archive.validate_collection(root)
        old_bytes=(root/f'estadisticas/{year}.json').read_bytes()
        previous=stats.validate(json.loads(old_bytes))
        if hashlib.sha256(old_bytes).hexdigest()!=value['expected_archive'] or rules.digest(dictionary)!=value['expected_dictionary']:raise ValueError('El histórico o el diccionario cambió. Prepará nuevamente la revisión.')
    start=datetime.now(timezone.utc).isoformat()
    blob=(export or admin.base.export_sheet)(source)
    sheets=admin.base.decode_xlsx(blob)
    def save_report(report,detail):
        report['sha256_fuente']=hashlib.sha256(blob).hexdigest()
        if not report_dir:return
        directory=Path(report_dir).resolve()
        if directory==root.resolve() or root.resolve() in directory.parents:raise ValueError('El informe administrativo debe quedar fuera del repositorio.')
        directory.mkdir(parents=True,exist_ok=True)
        (directory/'resumen.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
        (directory/'detalle_admin.enc.json').write_text(json.dumps(admin.seal(detail,(root/'_ftr_admin/diagnostico_publica.pem').read_bytes())),encoding='utf-8')
    try:
        data,report,detail=historical.build(sheets,year,source,start,dictionary,allow_partial=value['allow_partial'])
    except historical.HistoricalValidationError as error:
        save_report(error.report,error.detail)
        raise
    if previous:
        review.unchanged_controls(previous,data)
        detail['novedades_sin_clasificar']['revision_mecanica']['archivo_publicado']=previous
        detail['novedades_sin_clasificar']['revision_mecanica']['sha256_archivo']=value['expected_archive']
        detail['novedades_sin_clasificar']['revision_mecanica']['sheetUrl']=value['sheetUrl']
    if action=='history-recalculate':
        capsule=detail['novedades_sin_clasificar']['revision_mecanica']
        if capsule['huella_registros']!=value['expected_records'] or review.fingerprint(data['anomalias'])!=value['expected_result']:
            raise ValueError('Los registros o el resultado cambiaron después de la vista previa. No se publicó; prepará la revisión otra vez.')
    if action=='history-review':
        save_report(report,detail)
        return []
    with tempfile.TemporaryDirectory(prefix='ftr-archivo-anual-') as temp:
        stage=Path(temp)
        shutil.copytree(root/'estadisticas',stage/'estadisticas')
        shutil.copyfile(root/'estadisticas_ftr.json',stage/'estadisticas_ftr.json')
        if action=='history-recalculate':
            updated=dict(previous,anomalias=data['anomalias'],interpretacion=data['interpretacion'])
            stats.validate(updated)
            index=archive.validate_collection(stage)
            body=archive.encoded(updated)
            prior=f'estadisticas/revisiones/{year}/{value["expected_archive"]}.json'
            evidence=f'estadisticas/revisiones/{year}/{hashlib.sha256(body).hexdigest()}-revision.json'
            (stage/prior).parent.mkdir(parents=True,exist_ok=True)
            (stage/prior).write_bytes(old_bytes)
            (stage/evidence).write_bytes(archive.encoded(dict(version=1,periodo=year,anterior=value['expected_archive'],nuevo=hashlib.sha256(body).hexdigest(),diccionario=data['interpretacion'],motor_revision=data['anomalias']['motor_revision'],huella_registros=capsule['huella_registros'],recalculo_utc=start)))
            path=f'estadisticas/{year}.json';(stage/path).write_bytes(body)
            index['periodos']=[archive.entry(updated,body) if r['periodo']==year else r for r in index['periodos']]
            (stage/stats.INDEX).write_bytes(archive.encoded(index));archive.validate_collection(stage)
            paths=[path,stats.INDEX,prior,evidence]
            # The completed report must point to the publication it verifies,
            # not the archive hash from before the authorized recalculation.
            capsule.update(estadisticas=updated,archivo_publicado=updated,
                sha256_anterior=value['expected_archive'],sha256_archivo=hashlib.sha256(body).hexdigest())
        else:paths=historical.add_archive(stage,data)
        manifest=json.loads((root/'ftr_publicacion.json').read_bytes())
        for name in paths:manifest['files_sha256'][name]=hashlib.sha256((stage/name).read_bytes()).hexdigest()
        (stage/'ftr_publicacion.json').write_text(json.dumps(manifest)+'\n',encoding='utf-8')
        paths.append('ftr_publicacion.json')
        save_report(report,detail)
        for name in paths:
            (root/name).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(stage/name,root/name)
    return paths

def main():
    action=os.environ.get('FTR_STATS_ACTION')
    paths=apply(ROOT,action,json.loads(os.environ.get('FTR_STATS_COMMAND','{}')),os.environ.get('FTR_EXPECTED',''),report_dir=os.environ.get('FTR_REPORTE_DIR'))
    if action=='history-review':
        print('Informe histórico protegido preparado. No se publicaron cambios.');return
    revision=worker.commit(ROOT,paths)
    if action in ('history-import','history-recalculate'):worker.build_pages(revision)
    print('Diccionario confirmado; aplicación pendiente de una lectura o revisión autorizada' if action=='dictionary-save' else 'Histórico publicado y verificado')

if __name__=='__main__':
    try:main()
    except (ValueError,admin.base.DiagnosisError) as exc:
        print(str(exc));raise SystemExit(1) from None
    except Exception:
        print('No se completó la operación administrativa. Revisá la ejecución; no se modificaron las fuentes.');raise SystemExit(1) from None
