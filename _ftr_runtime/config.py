"""Contrato único para panel, lector, agendas y publicación FTR."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ZONE = 'America/Argentina/Buenos_Aires'
FILE = '_ftr_config.json'


def clean_config(value):
    if not isinstance(value, dict):
        raise ValueError('La configuración debe ser un objeto.')
    if type(value.get('period')) is not int or not 2000 <= value['period'] <= 2100:
        raise ValueError('El período debe estar entre 2000 y 2100.')
    link = value.get('sheetUrl', '')
    if not isinstance(link, str) or len(link) > 1000:
        raise ValueError('El enlace de la planilla no es válido.')
    u = urlparse(link)
    m = re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]{20,100})(?:/.*)?', u.path)
    if u.scheme != 'https' or u.netloc != 'docs.google.com' or not m:
        raise ValueError('Pegá el enlace HTTPS de una hoja de Google Sheets.')
    anchor = value.get('anchor', '')
    try:
        anchor = date.fromisoformat(anchor).isoformat()
    except (ValueError, TypeError):
        raise ValueError('La fecha del calendario no es válida.') from None
    result = dict(version=2, period=value['period'], sheetUrl='https://docs.google.com/spreadsheets/d/'+m[1]+'/edit', anchor=anchor, timezone=ZONE)
    for key in ('drive', 'cnrt'):
        schedule = value.get(key)
        if not isinstance(schedule, dict) or type(schedule.get('days')) is not int or not 1 <= schedule['days'] <= 60:
            raise ValueError('La frecuencia debe ser de 1 a 60 días.')
        if type(schedule.get('enabled')) is not bool or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', str(schedule.get('time', ''))):
            raise ValueError('Comprobá el horario y el estado de cada agenda.')
        result[key] = {k: schedule[k] for k in ('days', 'time', 'enabled')}
    lines = value.get('lines')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 500:
        raise ValueError('Se necesitan entre 1 y 500 líneas.')
    seen = set()
    result['lines'] = []
    for line in lines:
        if not isinstance(line, dict) or type(line.get('line')) is not int or not 1 <= line['line'] <= 99999:
            raise ValueError('Hay un número de línea no válido.')
        if line['line'] in seen:
            raise ValueError('Una línea está repetida en la configuración.')
        if type(line.get('company')) is not int or not 1 <= line['company'] <= 999999999 or type(line.get('enabled')) is not bool:
            raise ValueError('Comprobá empresa y estado de cada línea.')
        seen.add(line['line'])
        result['lines'].append({k: line[k] for k in ('line', 'company', 'enabled')})
    result['lines'].sort(key=lambda l: l['line'])
    if not any(l['enabled'] for l in result['lines']):
        raise ValueError('Debe quedar al menos una línea habilitada.')
    return result


def load(root):
    return clean_config(json.loads((Path(root)/FILE).read_text(encoding='utf-8-sig')))


def encoded(config):
    return (json.dumps(clean_config(config), ensure_ascii=False, indent=2)+'\n').encode()


def digest(config):
    return hashlib.sha256(encoded(config)).hexdigest()


def enabled(config):
    return {l['line']: l['company'] for l in config['lines'] if l['enabled']}


def sheet_identity(config):
    return config['period'], config['sheetUrl']


def current_slot(config, key, now):
    """Último turno del calendario, sin desplazarlo por ejecuciones manuales."""
    if now.tzinfo is None:
        raise ValueError('Se necesita una fecha con zona horaria.')
    when = now.astimezone(ZoneInfo(ZONE))
    start = date.fromisoformat(config['anchor'])
    n = (when.date()-start).days // config[key]['days']
    if n < 0:
        return None
    hour, minute = map(int, config[key]['time'].split(':'))
    day = start + timedelta(days=n*config[key]['days'])
    slot = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(ZONE))
    if slot > when:
        slot -= timedelta(days=config[key]['days'])
    if slot.date() < start:
        return None
    fingerprint = hashlib.sha256(json.dumps([config[key]['days'], config[key]['time'], config['anchor'], ZONE]).encode()).hexdigest()[:12]
    return fingerprint+':'+slot.isoformat()


def due(config, state, key, now):
    if not config[key]['enabled']:
        return False
    slot = current_slot(config, key, now)
    if slot is None or state.get(key, {}).get('served_slot') == slot:
        return False
    row = state.get(key, {})
    row = row.get('recurrence', row)
    last = row.get('attempt_utc')
    # La espera de reintento corresponde a errores, no a una lectura exitosa.
    # Una lectura manual anterior al turno no debe retrasar ese turno.
    if last and row.get('status') != 'success':
        try:
            if now - datetime.fromisoformat(last) < timedelta(hours=1):
                return False
        except ValueError:
            pass
    return True


def selected(config, old, state, mode, now):
    if mode in ('oneoff-set','oneoff-cancel','oneoff'):
        return []
    if mode == 'scheduled':
        return [key for key in ('cnrt', 'drive') if due(config, state, key, now)]
    if mode in ('drive', 'cnrt'):
        return [mode]
    if mode == 'all':
        return ['cnrt', 'drive']
    if mode == 'diagnostic':
        return ['drive']
    if mode == 'config':
        if enabled(config) != enabled(old):
            return ['cnrt', 'drive']
        return ['drive'] if sheet_identity(config) != sheet_identity(old) else []
    raise ValueError('Acción no reconocida.')
