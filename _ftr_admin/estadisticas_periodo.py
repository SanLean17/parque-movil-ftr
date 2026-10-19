"""Estadísticas explicadas del período. Lectura de prueba; no publica CSV.

Amplía el diagnóstico existente sin alterar su lector, validación de dominios,
incidencias o cifrado. Todos los resultados se cuentan por REGISTRO válido,
no como situación actual de los vehículos. No interpreta NOVEDADES.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DEFINICIONES = {
    'registros_validos': 'Filas válidas de fiscalización del período. Un vehículo puede aparecer varias veces.',
    'unidades_unicas_por_linea': 'Dominios diferentes dentro de cada línea; cada par línea-dominio se cuenta una sola vez.',
    'unidades_repetidas': 'Vehículos que aparecen en dos o más registros de su línea. Cada vehículo cuenta una vez.',
    'repeticiones_adicionales': 'Registros que quedan después del primero de cada vehículo: registros menos vehículos diferentes.',
    'fuera_de_servicio': 'Registros cuyo ESTADO dice Fuera de servicio. No significa vehículos actualmente fuera de servicio.',
    'observado': 'Registros cuyo ESTADO dice Observado. No se infiere a partir de novedades ni errores de carga.',
    'sin_novedad': 'Registros cuyo ESTADO dice Sin novedad.',
    'estado_vacio': 'Registros sin valor en ESTADO, incluida una tabla que no tenga esa columna.',
    'estado_otro': 'Registros con otro valor en ESTADO. No se lo asigna por suposición a una categoría.',
    'unidades_fuera_de_servicio': 'Dominios diferentes de la línea con al menos un registro Fuera de servicio en el período.',
    'duplicados_exactos_adicionales': 'Repeticiones de fecha, dominio e interno. Son posibles duplicados; no se eliminan automáticamente.',
    'parque_publicado': 'Dominios únicos del parque comparado, de la revisión de GitHub indicada. No es una descarga nueva de CNRT.',
}


def clasificar_estado(value):
    value = '' if value is None else str(value).strip()
    if not value:
        return 'estado_vacio'
    folded = ''.join(c for c in unicodedata.normalize('NFD', value) if not unicodedata.combining(c))
    key = re.sub(r'[^a-z0-9]', '', folded.lower())
    return {'fueradeservicio': 'fuera_de_servicio', 'observado': 'observado', 'sinnovedad': 'sin_novedad'}.get(key, 'estado_otro')


def completar_estadisticas(report, source_events, today):
    """Valida y completa un informe en memoria; no escribe fuentes o CSV."""
    enabled = {r['linea'] for r in report['lineas']}
    grouped = defaultdict(list)
    for e in source_events:
        dt = e.get('fecha')
        if e.get('linea') in enabled and dt is not None and dt.year == report['periodo'] and dt <= today and e.get('dominio'):
            grouped[e['linea']].append(e)
    keys = ('fuera_de_servicio', 'observado', 'sin_novedad', 'estado_vacio', 'estado_otro')
    total_status = Counter()
    for row in report['estadisticas']:
        events = grouped[row['linea']]
        domains = Counter(e['dominio'] for e in events)
        counts = Counter(clasificar_estado(e.get('estado')) for e in events)
        repeated = sum(n > 1 for n in domains.values())
        extra = sum(n - 1 for n in domains.values())
        if len(events) != row['registros_periodo'] or len(domains) != (row.get('dominios_unicos') or 0):
            raise ValueError('Las estadísticas no coinciden con las filas válidas del lector.')
        if extra != row['repeticiones_adicionales'] or repeated != row['unidades_repetidas']:
            raise ValueError('Los indicadores de repeticiones no coinciden con el diagnóstico.')
        if counts['fuera_de_servicio'] != row.get('fuera_de_servicio', 0) or counts['sin_novedad'] != row.get('sin_novedad', 0):
            raise ValueError('Los resultados existentes no coinciden con la clasificación de ESTADO.')
        if sum(counts.values()) != len(events):
            raise ValueError('Cada registro debe tener una única clasificación de resultado.')
        known = row['pestana_encontrada']
        for key in keys:
            row[key] = counts[key] if known else None
        row['estado_no_clasificado'] = counts['estado_vacio'] + counts['estado_otro'] if known else None
        row['registros_sin_columna_estado'] = sum(not e.get('tiene_estado', False) for e in events) if known else None
        row['unidades_observadas'] = len({e['dominio'] for e in events if clasificar_estado(e.get('estado')) == 'observado'}) if known else None
        row['unidades_sin_novedad'] = len({e['dominio'] for e in events if clasificar_estado(e.get('estado')) == 'sin_novedad'}) if known else None
        total_status.update(counts)
    totals = report['totales_estadisticas']
    totals.update(registros_observados=total_status['observado'], registros_sin_novedad=total_status['sin_novedad'],
                  registros_sin_estado=total_status['estado_vacio'], registros_otro_estado=total_status['estado_otro'],
                  lineas_con_observados=sum((r.get('observado') or 0) > 0 for r in report['estadisticas']))
    if sum(total_status.values()) != totals['registros_validos']:
        raise ValueError('Los resultados no suman el total de registros válidos del período.')
    if totals['registros_validos'] - totals['unidades_unicas_por_linea'] != totals['repeticiones_adicionales']:
        raise ValueError('El total de repeticiones adicionales no coincide.')
    report['estadisticas_version'] = 4
    report['definiciones_estadisticas'] = DEFINICIONES
    report['nota_resultados'] = 'Los resultados describen cada inspección en su fecha, no el estado actual del vehículo. Parque actual es referencia: no es el denominador de los resultados históricos.'
    report['ejemplo_repeticiones'] = 'Un vehículo aparece 3 veces y otro 2 veces: son 2 vehículos repetidos y 3 registros adicionales (2 + 1).'
    return report


def resumen_estadistico(report):
    fields = [('Línea', 'linea'), ('Parque actual', 'parque_publicado'), ('Registros del período', 'registros_periodo'),
              ('Fuera de servicio', 'fuera_de_servicio'), ('Observado', 'observado'), ('Sin novedad', 'sin_novedad'),
              ('Sin estado', 'estado_vacio'), ('Otro estado', 'estado_otro')]
    out = ['\n## Resultados de las inspecciones del período\n', report['nota_resultados'], '',
           '| ' + ' | '.join(x[0] for x in fields) + ' |', '|' + '|'.join(['---'] * len(fields)) + '|']
    for r in report['estadisticas']:
        out.append('| ' + ' | '.join('—' if r.get(k) is None else str(r[k]) for _, k in fields) + ' |')
    out += ['', '## Cómo leer los indicadores', '', report['ejemplo_repeticiones'], '']
    out += [f"**{k}:** {v}" for k, v in DEFINICIONES.items()]
    return '\n'.join(out)


def main():
    import diagnostico_administrativo as admin
    base = admin.base
    started = datetime.now(timezone.utc).isoformat()
    report, encrypted, failed = {}, None, True
    directory = Path(os.environ.get('FTR_REPORTE_DIR', str(Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'ftr-prueba-planilla'))).resolve()
    if directory == base.ROOT or base.ROOT in directory.parents:
        raise base.DiagnosisError('El informe debe guardarse fuera del repositorio.')
    try:
        year = int(os.environ.get('FTR_PERIODO', '2026'))
        if not 2000 <= year <= 2100:
            raise base.DiagnosisError('Período inválido.')
        identifier = base.spreadsheet_id(os.environ.get('FTR_SHEET_URL', ''))
        today = datetime.now(ZoneInfo('America/Argentina/Buenos_Aires')).date()
        configured = base.configuration(base.ROOT)
        public_pem = (Path(__file__).parent / 'diagnostico_publica.pem').read_bytes()
        sheets = base.decode_xlsx(base.export_sheet(identifier))
        report, records = base.analyze(sheets, configured, year, today=today)
        base.add_comparison(report, records, base.ROOT)
        details = admin.extend_report(report, sheets, base.ROOT, configured, identifier, started, today=today)
        completar_estadisticas(report, admin.source_rows(sheets), today)
        for name in ('ultima_actualizacion_parque.txt', 'ultima_actualizacion.txt'):
            path = base.ROOT / name
            if path.exists():
                try:
                    value = datetime.fromisoformat(path.read_text(encoding='utf-8-sig').strip().replace('Z', '+00:00'))
                    report['fecha_parque_comparado_utc'] = value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat()
                except ValueError:
                    pass
                break
        details['estadisticas_version'] = 4
        encrypted = admin.seal(details, public_pem)
        failed = not report['listo_para_revision_de_integracion']
    except base.DiagnosisError as exc:
        report = {'modo': 'DIAGNOSTICO_SIN_PUBLICAR', 'estado': 'ERROR', 'error': str(exc)}
    except Exception as exc:
        report = {'modo': 'DIAGNOSTICO_SIN_PUBLICAR', 'estado': 'ERROR', 'error': f'No se completó el diagnóstico ({type(exc).__name__}). Se conservó producción.'}
    report.update(inicio_lectura_utc=started, fin_prueba_utc=datetime.now(timezone.utc).isoformat(), revision_repositorio=os.environ.get('GITHUB_SHA', 'local'))
    summary = base.markdown(report)
    if 'totales_estadisticas' in report:
        summary += '\n\n## Totales administrativos\n\n```json\n' + json.dumps(report['totales_estadisticas'], ensure_ascii=False, indent=2) + '\n```\n'
        summary += resumen_estadistico(report)
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(summary + '\n')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'resumen.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (directory / 'resumen.md').write_text(summary + '\n', encoding='utf-8')
    if encrypted is not None:
        (directory / 'detalle_admin.enc.json').write_text(json.dumps(encrypted), encoding='utf-8')
    return 2 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
