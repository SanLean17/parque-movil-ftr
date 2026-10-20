"""Destacados del período para el panel local. No publica ni altera los bots.

Las visitas por línea son fechas distintas con controles válidos (no operativos
identificados). Los empates se conservan. Patentes e internos solo en el detalle
cifrado. Los rankings se recalculan en cada lectura, no se fijan en el HTML.
"""
from __future__ import annotations
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


def lideres(values, metric):
    positive = {int(k): int(v) for k, v in values.items() if v is not None and v > 0}
    maximum = max(positive.values(), default=0)
    return {'cantidad': maximum, 'lineas': sorted(k for k, v in positive.items() if v == maximum), 'criterio': metric}


def agregar_destacados(report, details, events, today):
    rows = {r['linea']: r for r in report['estadisticas']}
    dates, units = defaultdict(set), defaultdict(list)
    counts = Counter()
    for e in events:
        d = e.get('fecha')
        if e.get('linea') not in rows or d is None or d.year != report['periodo'] or d > today or not e.get('dominio'):
            continue
        dates[e['linea']].add(d)
        counts[e['linea']] += 1
        units[e['linea'], e['dominio']].append(e)
    for n, row in rows.items():
        if counts[n] != row['registros_periodo']:
            raise ValueError('Los destacados no coinciden con los registros validados.')
        row['fechas_con_controles'] = len(dates[n]) if row['pestana_encontrada'] else None
    maximum = max((len(v) for v in units.values()), default=0)
    winners = []
    for (n, domain), evs in sorted(units.items()):
        if len(evs) != maximum:
            continue
        last = max(e['fecha'] for e in evs)
        internals = sorted({e.get('interno', '') for e in evs if e['fecha'] == last and e.get('interno', '')})
        winners.append({'linea': n, 'dominio': domain, 'controles': maximum,
                        'internos_ultimo_control': internals, 'ultima_fecha': last.isoformat()})
    report['destacados_version'] = 1
    report['destacados'] = {
        'lineas_mas_visitadas': lideres({n: r['fechas_con_controles'] for n, r in rows.items()}, 'fechas_distintas_con_controles'),
        'lineas_mas_fuera_de_servicio': lideres({n: r.get('fuera_de_servicio') for n, r in rows.items()}, 'registros_fuera_de_servicio'),
        'lineas_mas_observados': lideres({n: r.get('observado') for n, r in rows.items()}, 'registros_observados'),
        'lineas_mas_controles': lideres(counts, 'registros_validos'),
        'unidades_mas_controladas': {'cantidad': maximum, 'cantidad_unidades': len(winners), 'criterio': 'registros_por_linea_y_dominio'},
    }
    details['destacados_unidades'] = {'cantidad': maximum, 'unidades': winners}
    report['nota_visitas'] = 'Una visita equivale a una fecha distinta con controles en esa línea. Varios controles en la misma fecha cuentan como una visita; no permite distinguir dos operativos del mismo día.'
    return report


def resumen_destacados(report):
    s = ['\n## Destacados del período', report['nota_visitas'], '', '| Indicador | Líneas empatadas | Cantidad |', '|---|---|---:|']
    for key, title in [('lineas_mas_visitadas','Líneas más visitadas'),('lineas_mas_fuera_de_servicio','Más fuera de servicio'),('lineas_mas_observados','Más observados'),('lineas_mas_controles','Más controles')]:
        item = report['destacados'][key]
        s.append('| ' + title + ' | ' + (', '.join(map(str,item['lineas'])) or 'Sin registros') + ' | ' + str(item['cantidad']) + ' |')
    return '\n'.join(s)


def main():
    import diagnostico_administrativo as admin
    import estadisticas_periodo as stats
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
        events = list(admin.source_rows(sheets))
        stats.completar_estadisticas(report, events, today)
        agregar_destacados(report, details, events, today)
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
        report = {'modo': 'DIAGNOSTICO_SIN_PUBLICAR', 'estado': 'ERROR', 'error': f'No se completó el diagnóstico ({type(exc).__name__}). Producción sin cambios.'}
    report.update(inicio_lectura_utc=started, fin_prueba_utc=datetime.now(timezone.utc).isoformat(), revision_repositorio=os.environ.get('GITHUB_SHA', 'local'))
    summary = base.markdown(report)
    if 'destacados' in report:
        summary += '\n\n## Totales administrativos\n\n```json\n' + json.dumps(report['totales_estadisticas'], ensure_ascii=False, indent=2) + '\n```\n'
        summary += resumen_destacados(report)
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
