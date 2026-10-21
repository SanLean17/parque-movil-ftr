"""Diagnóstico administrativo, sin publicar ni modificar fuentes.

Resumen público agregado. Detalles de fiscalizaciones cifrados para el panel
local: la clave privada de lectura de informes nunca se sube al repositorio.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_ftr_pruebas"))
import planilla_anual as base

CODES = {
    'DOMINIO_INVALIDO': ('error', 'El dominio no cumple el formato admitido. Revisá el dato original; no se corrige automáticamente.'),
    'FECHA_INVALIDA': ('error', 'Falta la fecha o no se reconoce como fecha válida.'),
    'FECHA_FUTURA': ('error', 'La fecha de control es posterior a la fecha de lectura.'),
    'LINEA_AUSENTE': ('error', 'La tabla tiene columna LÍNEA pero esta fila no identifica una línea válida.'),
    'INTERNO_AUSENTE': ('advertencia', 'Falta el interno. Un dominio válido conserva su control; revisá la carga.'),
    'LINEA_DIFIERE_TITULO': ('advertencia', 'La fila indica una línea distinta del encabezado. Se respeta la columna LÍNEA.'),
    'NO_EN_PARQUE': ('informacion', 'No se encontró este dominio en el parque comparado. No demuestra una baja ni un error de carga.'),
    'INTERNO_DIFIERE': ('advertencia', 'El dominio aparece en el parque con otro interno. Puede haber reasignaciones; no se corrige por suposición.'),
    'LINEA_NO_HABILITADA': ('informacion', 'La línea está en la planilla, pero no está habilitada en la web. Se conserva en el diagnóstico, fuera del conteo activo.'),
    'OTRO_PERIODO': ('informacion', 'Registro de otro año, excluido del conteo del período seleccionado.'),
}


def internal(value):
    s = base.text(value)
    return str(int(float(s))) if re.fullmatch(r'\d+(?:\.0+)?', s) else s.upper()


def colname(number):
    out = ''
    while number:
        number, rest = divmod(number - 1, 26)
        out = chr(65 + rest) + out
    return out


def fleet_rows(root, number):
    path = root / 'parques' / f'linea{number}.csv'
    if not path.exists():
        return None
    raw = path.read_bytes()
    try:
        raw = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raw = raw.decode('cp1252')
    header = next((x for x in raw.splitlines() if x.strip()), '')
    if not header:
        raise base.DiagnosisError('Un parque publicado no tiene encabezados.')
    sep = max((';', ',', '\t'), key=lambda c: len(next(csv.reader([header], delimiter=c))))
    reader = csv.DictReader(io.StringIO(raw), delimiter=sep, strict=True)
    names = {base.norm(x): x for x in reader.fieldnames or []}
    dom = next((names[k] for k in base.HEADERS['dominio'] if k in names), None)
    intr = next((names[k] for k in base.HEADERS['interno'] if k in names), None)
    lin = names.get('linea')
    if not dom or not intr:
        raise base.DiagnosisError('Un parque publicado no tiene DOMINIO/INTERNO; se detuvo la comparación.')
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise base.DiagnosisError('Un parque tiene columnas desalineadas. No se omiten filas silenciosamente.')
        if lin and base.text(row[lin]):
            ids = {base.line_number(x.strip()) for x in re.split(r'[,;/|]', row[lin])}
            if number not in ids:
                continue
        d = base.plate(row[dom])
        if d:
            rows.append({'dominio': d, 'interno': internal(row[intr])})
    return rows


def candidates(rows, value):
    """Solo el mismo interno de la MISMA línea. Referencia, nunca corrección."""
    if rows is None or not internal(value):
        return []
    unique = {(x['dominio'], x['interno']) for x in rows if x['interno'] == internal(value)}
    return [{'dominio': d, 'interno': i} for d, i in sorted(unique)]


def source_rows(sheets):
    """Comparte detección de tablas con el lector ya probado; no lee NOVEDADES."""
    for pos, sheet in enumerate(sheets, 1):
        if base.norm(sheet.name) == 'tablerodecontrol':
            continue
        found = base.blocks(sheet)
        for block in found:
            cols, expected = block['cols'], block['ids']
            by_row = 'linea' in cols
            if not by_row and (len(expected) != 1 or block['conflict']):
                continue
            end = min((b['row'] for b in found if b['row'] > block['row'] and b['left'] <= block['right'] and b['right'] >= block['left']), default=max((r for r, _ in sheet.cells), default=0) + 1)
            following = min((b['left'] for b in found if b['row'] == block['row'] and b['left'] > block['left']), default=2049)
            states = [c for (r, c), v in sheet.cells.items() if r == block['row'] and block['left'] <= c < following and base.norm(v) == 'estado']
            state_col = states[0] if len(states) == 1 else None
            for row in range(block['row'] + 1, end):
                values = {k: sheet.get(row, c) for k, c in cols.items()}
                if not any(base.text(values.get(k)) for k in ('fecha', 'dominio', 'interno')):
                    continue
                if any(base.title_lines(sheet.cells.get((row, c))) for c in range(block['left'], block['right'] + 1)) and not base.plate(values.get('dominio')):
                    break
                number = base.line_number(values.get('linea')) if by_row else next(iter(expected))
                yield {'pestana': sheet.name, 'pestana_posicion': pos, 'fila': row,
                       'linea': number, 'cols': cols, 'values': values,
                       'fecha': base.parse_date(values.get('fecha'), sheet.epoch1904),
                       'dominio': base.plate(values.get('dominio')), 'interno': internal(values.get('interno')),
                       'estado': base.norm(sheet.get(row, state_col)) if state_col else '',
                       'tiene_estado': state_col is not None,
                       'conflicto_titulo': bool(by_row and expected and number not in expected)}


def extend_report(report, sheets, root, configured, identifier, detected_at, today=None):
    today = today or datetime.now(ZoneInfo('America/Argentina/Buenos_Aires')).date()
    fleets = {n: fleet_rows(root, n) for n in configured}
    issues, events, unknown_events = [], [], []
    stats = defaultdict(Counter)

    def add(code, event, field='dominio'):
        category, message = CODES[code]
        values = event['values']
        column = event['cols'].get(field, event['cols']['dominio'])
        entry = {k: event[k] for k in ('linea', 'pestana', 'pestana_posicion', 'fila')}
        entry.update({'codigo': code, 'categoria': category, 'mensaje': message,
            'fecha_control': event['fecha'].isoformat() if event['fecha'] else '',
            'fecha_ingresada': base.text(values.get('fecha')),
            'dominio_ingresado': base.text(values.get('dominio')),
            'interno': event['interno'], 'campo': field, 'celda': f'{colname(column)}{event["fila"]}',
            'detectado_utc': detected_at, 'candidatos_mismo_interno': candidates(fleets.get(event['linea']), event['interno']),
            'archivo_url': f'https://docs.google.com/spreadsheets/d/{identifier}/edit'})
        park = root / 'parques' / f"linea{event['linea']}.csv"
        stamp = root / 'ultima_actualizacion_parque.txt'
        entry['referencia_parque'] = {
            'archivo': f"parques/linea{event['linea']}.csv" if park.is_file() else None,
            'sha256': hashlib.sha256(park.read_bytes()).hexdigest() if park.is_file() else None,
            'fecha_lectura_utc': stamp.read_text(encoding='utf-8-sig').strip() if stamp.is_file() else None,
        }
        fingerprint = json.dumps([identifier, entry['pestana_posicion'], entry['fila'], code, entry['fecha_ingresada'], entry['dominio_ingresado'], entry['interno']], ensure_ascii=False)
        entry['id'] = hashlib.sha256(fingerprint.encode()).hexdigest()[:24]
        issues.append(entry)

    for event in source_rows(sheets):
        number, dt, domain = event['linea'], event['fecha'], event['dominio']
        if number is None:
            add('LINEA_AUSENTE', event, 'linea')
            continue
        if dt is not None and dt.year != report['periodo']:
            add('OTRO_PERIODO', event, 'fecha')
            continue
        if number not in configured:
            add('LINEA_NO_HABILITADA', event, 'linea')
            unknown_events.append(event)
            continue
        valid = True
        if dt is None:
            add('FECHA_INVALIDA', event, 'fecha'); valid = False
        elif dt > today:
            add('FECHA_FUTURA', event, 'fecha'); valid = False
        if not domain:
            add('DOMINIO_INVALIDO', event); valid = False
        if not valid:
            continue
        if not event['interno']:
            add('INTERNO_AUSENTE', event, 'interno')
        if event['conflicto_titulo']:
            add('LINEA_DIFIERE_TITULO', event, 'linea')
        events.append(event)
        rows = fleets[number]
        if rows is not None:
            matching = [x for x in rows if x['dominio'] == domain]
            if not matching:
                add('NO_EN_PARQUE', event)
            elif event['interno'] and all(x['interno'] != event['interno'] for x in matching):
                add('INTERNO_DIFIERE', event, 'interno')
        status = event['estado']
        stats[number]['registros_con_columna_estado'] += int(event['tiene_estado'])
        if status == 'fueradeservicio':
            stats[number]['fuera_de_servicio'] += 1
        elif status == 'sinnovedad':
            stats[number]['sin_novedad'] += 1
        else:
            stats[number]['estado_no_clasificado'] += 1

    grouped = defaultdict(list)
    for event in events:
        grouped[event['linea'], event['dominio']].append(event)
    repeats = []
    for (number, domain), group in sorted(grouped.items()):
        if len(group) < 2:
            continue
        visits = sorted(group, key=lambda x: (x['fecha'], x['pestana_posicion'], x['fila']))
        repeats.append({'linea': number, 'dominio': domain, 'veces': len(group), 'adicionales': len(group) - 1,
            'controles': [{'fecha': e['fecha'].isoformat(), 'interno': e['interno'], 'pestana': e['pestana'], 'pestana_posicion': e['pestana_posicion'], 'fila': e['fila']} for e in visits]})

    public_stats = []
    for item in report['lineas']:
        number = item['linea']
        evs = [e for e in events if e['linea'] == number]
        distinct = {e['dominio'] for e in evs}
        if len(evs) != item['registros_periodo'] or (item['dominios_unicos'] is not None and len(distinct) != item['dominios_unicos']):
            raise base.DiagnosisError('El diagnóstico ampliado no coincide con el lector base. Se detuvo para no mostrar estadísticas inconsistentes.')
        pair_counts = Counter(e['dominio'] for e in evs)
        exact_counts = Counter((e['dominio'], e['fecha'], e['interno']) for e in evs)
        fleet = fleets[number]
        ds = {x['dominio'] for x in fleet} if fleet is not None else None
        covered = len(distinct & ds) if ds is not None and item['pestana_encontrada'] else None
        row = {**item, **dict(stats[number]), 'unidades_repetidas': sum(n > 1 for n in pair_counts.values()),
            'repeticiones_adicionales': len(evs) - len(distinct),
            'duplicados_exactos_adicionales': sum(n-1 for n in exact_counts.values()),
            'unidades_fuera_de_servicio': len({e['dominio'] for e in evs if e['estado'] == 'fueradeservicio'}),
            'pendientes_actuales': len(ds) - covered if ds is not None and covered is not None else None,
            'cobertura_actual_pct': round(100 * covered / len(ds), 1) if ds and covered is not None else None,
            'errores_carga': sum(x['categoria'] == 'error' and x['linea'] == number for x in issues),
            'advertencias': sum(x['categoria'] == 'advertencia' and x['linea'] == number for x in issues)}
        for key in ('fuera_de_servicio', 'sin_novedad', 'estado_no_clasificado', 'registros_con_columna_estado'):
            row.setdefault(key, 0)
        public_stats.append(row)
    category_counts = Counter(x['categoria'] for x in issues)
    code_counts = Counter(x['codigo'] for x in issues)
    report['admin_version'] = 3
    report['estadisticas'] = public_stats
    report['incidencias_resumen'] = {'por_categoria': dict(category_counts), 'por_tipo': dict(code_counts),
        'lineas_con_errores': len({x['linea'] for x in issues if x['categoria'] == 'error' and x['linea'] is not None}),
        'ubicaciones': [{k: x[k] for k in ('codigo', 'categoria', 'pestana_posicion', 'fila', 'linea', 'campo', 'celda')} for x in issues]}
    report['totales_estadisticas'] = {
        'registros_validos': len(events), 'unidades_unicas_por_linea': len(grouped),
        'repeticiones_adicionales': len(events)-len(grouped), 'unidades_repetidas': len(repeats),
        'duplicados_exactos_adicionales': sum(x['duplicados_exactos_adicionales'] for x in public_stats),
        'registros_fuera_de_servicio': sum(x['fuera_de_servicio'] for x in public_stats),
        'lineas_con_fuera_de_servicio': sum(x['fuera_de_servicio'] > 0 for x in public_stats),
        'registros_lineas_no_habilitadas': len(unknown_events)}
    report['listo_para_revision_de_integracion'] = not category_counts['error'] and not report['lineas_habilitadas_no_encontradas'] and not report['ubicaciones_a_revisar']
    report['detalles_privados'] = 'CIFRADOS_PARA_PANEL_LOCAL'
    email = ''
    try:
        email = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON', '{}')).get('client_email', '')
    except (ValueError, AttributeError):
        pass
    if re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com', email):
        report['correo_bot_lector'] = email
    return {'version': 3, 'modo': 'DIAGNOSTICO_PRIVADO_SIN_PUBLICAR', 'periodo': report['periodo'],
        'detectado_utc': detected_at, 'revision_repositorio': os.environ.get('GITHUB_SHA', 'local'),
        'incidencias': issues, 'repetidos': repeats,
        'nota': 'El parque comparado es la revisión indicada, no una nueva descarga. Mismo interno no demuestra identidad histórica. Nunca se corrigen celdas ni se confirma una baja.'}


def seal(payload, public_pem):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072:
        raise base.DiagnosisError('La clave pública de informes no es válida.')
    symmetric = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    aad = b'FTR-DIAGNOSTICO-3'
    ciphertext = AESGCM(symmetric).encrypt(nonce, json.dumps(payload, ensure_ascii=False).encode(), aad)
    wrapped = key.encrypt(symmetric, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    enc = lambda b: base64.b64encode(b).decode('ascii')
    return {'format': 'FTR-DIAGNOSTICO-3', 'algorithm': 'RSA-OAEP-SHA256+A256GCM',
        'wrapped_key': enc(wrapped), 'nonce': enc(nonce), 'ciphertext': enc(ciphertext),
        'public_key_id': hashlib.sha256(public_pem).hexdigest()[:16]}


def main():
    start = datetime.now(timezone.utc).isoformat()
    report, encrypted = {}, None
    failed = False
    try:
        year, identifier = base.source_settings(base.ROOT)
        configured = base.configuration(base.ROOT)
        public_pem = (Path(__file__).parent / 'diagnostico_publica.pem').read_bytes()
        sheets = base.decode_xlsx(base.export_sheet(identifier))
        report, records = base.analyze(sheets, configured, year)
        base.add_comparison(report, records, base.ROOT)
        details = extend_report(report, sheets, base.ROOT, configured, identifier, start)
        encrypted = seal(details, public_pem)
        failed = not report['listo_para_revision_de_integracion']
    except base.DiagnosisError as exc:
        report = {'modo': 'DIAGNOSTICO_SIN_PUBLICAR', 'estado': 'ERROR', 'error': str(exc)}
        failed = True
    except Exception as exc:
        report = {'modo': 'DIAGNOSTICO_SIN_PUBLICAR', 'estado': 'ERROR', 'error': f'No se completó el diagnóstico ({type(exc).__name__}). No se modificaron fuentes ni producción.'}
        failed = True
    report.update(inicio_lectura_utc=start, fin_prueba_utc=datetime.now(timezone.utc).isoformat(), revision_repositorio=os.environ.get('GITHUB_SHA', 'local'))
    summary = base.markdown(report)
    if 'totales_estadisticas' in report:
        summary += '\n\n## Estadísticas y avisos administrativos\n\n```json\n' + json.dumps(report['totales_estadisticas'], ensure_ascii=False, indent=2) + '\n```\n'
        summary += '\nLos detalles de dominios e internos están cifrados. Ausencia del parque y línea no habilitada son información, no bajas oficiales.\n'
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(summary + '\n')
    directory = Path(os.environ.get('FTR_REPORTE_DIR', str(Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'ftr-prueba-planilla'))).resolve()
    if directory == base.ROOT or base.ROOT in directory.parents:
        raise base.DiagnosisError('El informe debe guardarse fuera del repositorio.')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'resumen.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (directory / 'resumen.md').write_text(summary + '\n', encoding='utf-8')
    if encrypted is not None:
        (directory / 'detalle_admin.enc.json').write_text(json.dumps(encrypted), encoding='utf-8')
    return 2 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
