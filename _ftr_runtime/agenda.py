"""Agenda observable, sin lecturas de Google/CNRT ni escrituras en repositorio.

Un cambio de horario entra en vigencia al guardarse: no recupera turnos del
horario anterior ni marca como leídos datos que no se consultaron.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .config import ZONE, current_slot, selected


def _instant(value):
    if not value:
        return None
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('La fecha de vigencia de la agenda no tiene zona horaria.')
    return result


def slot_time(slot):
    return _instant(slot.split(':', 1)[1]) if slot else None


def eligible_slot(config, state, key, now):
    slot = current_slot(config, key, now)
    effective = _instant(state.get(key, {}).get('schedule_effective_from_utc'))
    if slot and effective and slot_time(slot) < effective:
        return None
    return slot


def select_jobs(config, old, state, mode, now):
    jobs = selected(config, old, state, mode, now)
    if mode != 'scheduled':
        return jobs
    return [key for key in jobs if eligible_slot(config, state, key, now)]


def activate_changed_schedules(old, config, state, now):
    """No toca read_utc, status ni served_slot: guardar no es leer fuentes."""
    if now.tzinfo is None:
        raise ValueError('Se necesita una fecha con zona horaria.')
    for key in ('drive', 'cnrt'):
        if old[key] != config[key] or old['anchor'] != config['anchor']:
            state.setdefault(key, {})['schedule_effective_from_utc'] = now.astimezone(timezone.utc).isoformat()


def next_slot_time(config, key, now):
    zone = ZoneInfo(ZONE)
    raw = current_slot(config, key, now)
    if raw:
        return slot_time(raw) + timedelta(days=config[key]['days'])
    start = date.fromisoformat(config['anchor'])
    h, m = map(int, config[key]['time'].split(':'))
    return datetime(start.year, start.month, start.day, h, m, tzinfo=zone)


def describe(config, state, now):
    """Estado derivado de la configuración PUBLICADA, no del borrador del panel."""
    result = {}
    jobs = select_jobs(config, config, state, 'scheduled', now)
    for key in ('drive', 'cnrt'):
        row = state.get(key, {})
        slot = eligible_slot(config, state, key, now)
        pending = bool(config[key]['enabled'] and slot and slot != row.get('served_slot'))
        late = max(0, int((now - slot_time(slot)).total_seconds() // 60)) if pending else 0
        state_name = ('disabled' if not config[key]['enabled'] else
                      'error' if pending and row.get('status') == 'error' else
                      'overdue' if pending and late >= 30 else 'pending' if pending else
                      'saved' if row.get('read_utc') else 'waiting')
        nxt = slot_time(slot) if pending else next_slot_time(config, key, now)
        result[key] = dict(status=state_name, pending=pending, eligible=key in jobs,
                           overdue_minutes=late, expected_slot=slot,
                           next_due_utc=nxt.astimezone(timezone.utc).isoformat() if config[key]['enabled'] else None,
                           last_read_utc=row.get('read_utc'), checked_at_utc=now.astimezone(timezone.utc).isoformat())
    return result


def explain(config, state, now, jobs, mode):
    states = describe(config, state, now)
    lines = ['## Comprobación de agenda FTR', '',
             'Modo: '+mode, 'Comprobación: '+now.astimezone(ZoneInfo(ZONE)).strftime('%d/%m/%Y %H:%M:%S')+' hs', '',
             '| Fuente | Frecuencia | Hora | Decisión |', '|---|---:|---|---|']
    for key, label in [('drive', 'Planilla anual FTR'), ('cnrt', 'Parque móvil CNRT')]:
        s = states[key]
        decision = ('Corresponde procesar' if key in jobs else
                    'Automatización desactivada' if not config[key]['enabled'] else
                    'Pendiente; espera de reintento' if s['pending'] else
                    'No corresponde una lectura nueva')
        lines.append(f"| {label} | {config[key]['days']} día(s) | {config[key]['time']} | {decision} |")
    if not jobs:
        lines += ['', 'Esta ejecución no lee Google ni CNRT. Comprobar la agenda NO significa actualizar los datos.']
    return '\n'.join(lines)+'\n'
