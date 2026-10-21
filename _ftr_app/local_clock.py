"""Respaldo opcional de agenda desde la PC. No lee Google/CNRT ni publica CSV.

Solo envía `scheduled` a GitHub; el coordinador remoto vuelve a comprobar
turnos, permisos, concurrencia y validación. Desactivado por defecto.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from _ftr_runtime.agenda import describe, select_jobs, eligible_slot
from _ftr_runtime.config import digest

BUSY = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
RETRY_SECONDS = 600


def read_json(path: Path, default: dict) -> dict:
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
        return result if isinstance(result, dict) else default.copy()
    except (OSError, ValueError):
        return default.copy()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(5) + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def computer_lock(path: Path):
    """Una sola comprobación por PC, incluso con dos ventanas del programa."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    acquired = False
    try:
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                pass
        yield acquired
    finally:
        if acquired:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class LocalClock:
    """Callbacks inyectables para probar el reloj sin Internet ni credenciales."""
    def __init__(self, directory, snapshot, runs, dispatch, operation_lock,
                 utcnow=None, interval=45.0):
        self.directory = directory
        self.snapshot = snapshot
        self.runs = runs
        self.dispatch = dispatch
        self.operation_lock = operation_lock
        self.utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self.interval = interval
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self._status_lock = threading.Lock()
        self._detail = dict(status='off', message='Respaldo de esta PC desactivado.')

    def file(self, name):
        return Path(self.directory()) / name

    def enabled(self):
        return read_json(self.file('reloj_pc.json'), {}).get('enabled') is True

    def set_enabled(self, value):
        if type(value) is not bool:
            raise ValueError('Elegí activar o desactivar el respaldo de esta PC.')
        write_json(self.file('reloj_pc.json'), {'enabled': value, 'version': 1})
        self._set('waiting' if value else 'off',
                  'Respaldo activado. Comprobando los horarios publicados...' if value else
                  'Respaldo desactivado. No se enviarán nuevas solicitudes desde esta PC.')
        self._wake.set()
        return self.status()

    def _set(self, status, message, **values):
        with self._status_lock:
            self._detail = dict(status=status, message=message,
                                checked_at_utc=self.utcnow().isoformat(), **values)

    def status(self):
        with self._status_lock:
            result = self._detail.copy()
        result['enabled'] = self.enabled()
        result['requires_open_pc'] = True
        result['check_seconds'] = self.interval
        return result

    def tick(self):
        if not self.enabled() or self._stop.is_set():
            return
        try:
            with computer_lock(self.file('reloj_pc.lock')) as acquired:
                if not acquired:
                    self._set('other_instance', 'Otra ventana de FTR está comprobando la agenda de esta PC.')
                    return
                with self.operation_lock:
                    if not self.enabled() or self._stop.is_set():
                        return
                    config, state, revision = self.snapshot()
                    instant = self.utcnow()
                    jobs = select_jobs(config, config, state, 'scheduled', instant)
                    timing = describe(config, state, instant)
                    if not jobs:
                        self._set('waiting', 'No hay turnos habilitados pendientes. Se conserva el calendario de GitHub.', schedule=timing)
                        return
                    runs = self.runs()
                    if any(r.get('status') in BUSY for r in runs):
                        self._set('busy', 'GitHub ya tiene un proceso en cola o en ejecución. No se envía otro.', schedule=timing)
                        return
                    slots = {key: eligible_slot(config, state, key, instant) for key in jobs}
                    signature = hashlib.sha256(json.dumps([digest(config), slots], sort_keys=True).encode()).hexdigest()
                    last = read_json(self.file('reloj_pc_envio.json'), {})
                    sent_at = last.get('attempt_utc')
                    if sent_at:
                        try:
                            previous = datetime.fromisoformat(sent_at)
                            if previous.tzinfo is None:
                                raise ValueError('sin zona')
                            age = (instant - previous).total_seconds()
                            if last.get('signature') == signature and age < RETRY_SECONDS:
                                self._set('awaiting', 'Ya se solicitó este turno. Esperando confirmación de GitHub antes de reintentar.',
                                          schedule=timing, request_id=last.get('request_id'), sent_at_utc=sent_at)
                                return
                        except ValueError:
                            self._set('error', 'No se pudo interpretar el registro del último envío; no se envía otro para evitar duplicados.')
                            return
                    if not self.enabled() or self._stop.is_set():
                        return
                    identifier = 'pc-auto-' + secrets.token_hex(8)
                    # Se registra ANTES del POST: timeout no equivale a rechazo.
                    marker = dict(signature=signature, request_id=identifier,
                                  attempt_utc=instant.isoformat(), sources=jobs,
                                  config_revision=revision, accepted=False)
                    write_json(self.file('reloj_pc_envio.json'), marker)
                    self.dispatch(identifier)
                    marker['accepted'] = True
                    write_json(self.file('reloj_pc_envio.json'), marker)
                    self._set('sent', 'Turno solicitado automáticamente desde esta PC. Falta que GitHub procese y publique el resultado.',
                              request_id=identifier, sources=jobs, sent_at_utc=instant.isoformat(), schedule=timing)
        except Exception:
            self._set('error', 'No se pudo completar la comprobación o confirmar el envío. Revisá Internet y Conexiones. Se conserva el último dato publicado; el programa reintentará sin repetir enseguida una solicitud incierta.')

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        def loop():
            while not self._stop.is_set():
                self.tick()
                self._wake.wait(self.interval)
                self._wake.clear()
        self._thread = threading.Thread(target=loop, name='FTR-reloj-PC', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set(); self._wake.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
