"""Órdenes confirmadas, persistentes y sin reloj de fuentes.

Una pérdida de respuesta después del POST es ambigua: se busca el identificador
en GitHub, pero nunca se repite automáticamente un envío que pudo aceptarse.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

from _ftr_runtime.config import clean_config, digest, encoded
from _ftr_app.local_clock import computer_lock, write_json
from _ftr_runtime import oneoff
from _ftr_app.queue_runs import utc

OPEN = {'pending', 'authorization', 'sending', 'unknown', 'sent', 'conflict'}
BUSY = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
LABELS = {
    'pending': 'Pendiente de envío', 'authorization': 'Pendiente: reconectar GitHub',
    'sending': 'Enviando solicitud', 'unknown': 'Envío por comprobar; no se repetirá',
    'sent': 'Solicitud enviada; esperando resultado', 'conflict': 'Orden detenida: revisar conflicto',
    'completed': 'Resultado confirmado en GitHub', 'failed': 'La operación terminó con error',
    'cancelled': 'Cancelada antes del envío',
    'resolved': 'Cerrada sin confirmar; no reenviada',
}


class AuthorizationError(ValueError):
    pass

class DispatchRejected(ValueError):
    def __init__(self, status):
        self.http_status=status
        super().__init__('GitHub rechazó el envío (HTTP '+str(status)+'). La orden se conserva para revisar; no se reenviará automáticamente.')

def queue_token(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


class Outbox:
    def __init__(self, directory, snapshot, runs, dispatch, clock=None):
        self.directory, self.snapshot, self.runs, self.dispatch = directory, snapshot, runs, dispatch
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.error = None

    def file(self, name):
        return Path(self.directory()) / name

    def read(self):
        path = self.file('ordenes.json')
        if not path.exists():
            return {'version': 1, 'orders': []}
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            assert value['version'] == 1 and isinstance(value['orders'], list)
            assert all(isinstance(r, dict) and r.get('status') in LABELS and
                       re.fullmatch(r'[a-f0-9]{32}', r.get('id', '')) for r in value['orders'])
            return value
        except (ValueError, KeyError, AssertionError, TypeError):
            raise ValueError('No se pudo leer la cola local. Se conserva el archivo; no se enviará ni descartará ninguna orden.') from None

    def save(self, value):
        write_json(self.file('ordenes.json'), value)

    def public(self, row):
        return {k: copy.deepcopy(v) for k, v in row.items() if k not in ('config', 'fingerprint')}

    def status(self):
        value=self.read();active=[r for r in value['orders'] if r['status'] in OPEN]
        first=active[0] if active else None
        needs_review=first and (first['status'] in ('unknown','sending','conflict','authorization') or
            first['status']=='sent' and not first.get('run_id') and self.clock()-utc(first.get('sent_at') or first['created_at'])>=timedelta(minutes=5))
        blocked=first if needs_review else None
        return dict(orders=[dict(self.public(r), label=LABELS[r['status']]) for r in value['orders']],error=self.error,
                    blocked=self.public(blocked) if blocked else None,paused=value.get('paused',False),confirmation=queue_token(value))

    def reconcile(self,row,runs):
        found=[r for r in runs if r.get('request_id')==row['id']]
        if len(found)>1 or any(r.get('action') not in (None,row['action']) for r in found):
            row.update(status='unknown',message='Hay ejecuciones contradictorias con el mismo identificador. Revisá la evidencia en GitHub.',resolution=None)
            return 'conflicting_matches'
        if not found:return 'not_found'
        run=found[0]
        row.update(run_id=run['id'],url=run.get('url'),run_status=run['status'],conclusion=run.get('conclusion'),effect=run.get('effect'),resolution=None)
        if run['status']!='completed':
            row.update(status='sent',message='Ejecución iniciada en GitHub.' if run['status']=='in_progress' else 'Solicitud aceptada por GitHub; ejecución en espera.')
        else:
            ok=run.get('conclusion')=='success' and run.get('effect') in ('configuration','updated','diagnostic','oneoff_saved','coalesced','publication','dictionary','historical','historical_review')
            status='completed' if ok else 'unknown' if run.get('conclusion')=='success' else 'failed'
            row.update(status=status,message=run.get('detail') or LABELS[status],
                publication_verified=bool(ok and run.get('effect') in ('updated','publication','historical','coalesced')))
        return 'found'

    def inspect(self,value,row):
        """Read-only remote reconciliation; never dispatches or advances the queue."""
        if row['status']=='sending':row.update(status='unknown',message=LABELS['unknown'])
        row['resolution']=None
        evidence=dict(checked_at=self.clock().isoformat(),complete=False,request_id=row['id'])
        try:
            runs=self.runs(row.get('sent_at') or row['created_at'])
            evidence.update(getattr(runs,'evidence',{}))
            evidence['checked_at']=self.clock().isoformat()
            evidence['matches']=[copy.deepcopy(r) for r in runs if r.get('request_id')==row['id']]
            evidence['result']=self.reconcile(row,runs)
            age=self.clock()-utc(row.get('sent_at') or row['created_at'])
            unresolved=evidence['result']=='not_found' or evidence['result']=='found' and row['status']=='unknown' and row.get('run_status')=='completed'
            if evidence['complete'] and unresolved and age>=timedelta(minutes=5):
                row['resolution']=dict(confirmation=secrets.token_hex(24),checked_at=self.clock().isoformat())
            elif age<timedelta(minutes=5):evidence['note']='Esperá cinco minutos desde el envío antes de resolver; GitHub puede demorar en mostrarlo.'
        except Exception as exc:
            evidence.update(complete=False,result='incomplete',message=str(exc) if isinstance(exc,ValueError) else 'No se pudo completar la consulta de GitHub. Revisá Internet y la autorización.')
        row.setdefault('checks',[]).append(evidence)
        self.save(value)
        return evidence

    def check(self,identifier):
        with self._lock,computer_lock(self.file('ordenes.lock')) as acquired:
            if not acquired:raise ValueError('La cola está ocupada. Esperá antes de comprobar.')
            value=self.read();row=next((r for r in value['orders'] if r['id']==identifier),None)
            if not row or row['status'] not in ('unknown','sending','sent'):raise ValueError('Esta orden no tiene un envío por comprobar.')
            self.inspect(value,row)
            return self.status()

    def resolve(self,identifier,confirmation):
        with self._lock,computer_lock(self.file('ordenes.lock')) as acquired:
            if not acquired:raise ValueError('La cola está ocupada. Reintentá la resolución.')
            value=self.read();row=next((r for r in value['orders'] if r['id']==identifier),None)
            permit=(row or {}).get('resolution') or {}
            if not confirmation or confirmation!=permit.get('confirmation') or row['status'] not in ('unknown','sent'):
                raise ValueError('Primero completá COMPROBAR ENVÍO EN GITHUB y revisá su resultado.')
            if self.clock()-utc(permit['checked_at'])>timedelta(minutes=5):raise ValueError('La comprobación venció. Consultá GitHub nuevamente.')
            evidence=self.inspect(value,row)  # Close the check/confirmation race with another complete scan.
            if not row.get('resolution') or not evidence['complete']:
                raise ValueError('El resultado cambió o la consulta no se completó. Revisá la evidencia; no se cerró la orden.')
            row.update(status='resolved',message=LABELS['resolved']+'. No afirma que GitHub la rechazó ni que se ejecutó.',
                       resolved_at=self.clock().isoformat(),resolution=None,publication_verified=False)
            value['paused']=True
            for child in value['orders']:
                if child.get('depends_on')==identifier and child['status'] in ('pending','authorization'):
                    child.update(status='conflict',message='La orden requerida se cerró sin confirmar. Cancelá y prepará esta orden nuevamente después de revisar GitHub.')
            self.save(value)
            return self.status()

    def validate_pending(self,row,remote):
        if remote['digest']!=row['expected']:raise ValueError('Cambió la configuración publicada. Cancelá esta orden y confirmá una nueva después de revisar los cambios.')
        if row['action'] in ('dictionary-save','history-import','history-review','history-recalculate'):
            from _ftr_runtime.statistics_commands import clean
            command=clean(row['action'],row['statistical'])
            if 'expected_dictionary' in command:
                if not remote.get('dictionary_digest'):raise ValueError('No se pudo verificar el diccionario publicado. Consultá GitHub antes de enviar.')
                if remote['dictionary_digest']!=command['expected_dictionary']:raise ValueError('Cambió el diccionario desde que se guardó esta orden. Cancelala y prepará una nueva vista previa; no se sobrescriben reglas posteriores.')

    def resume(self,confirmation):
        with self._lock,computer_lock(self.file('ordenes.lock')) as acquired:
            if not acquired:raise ValueError('La cola está ocupada.')
            value=self.read()
            if not value.get('paused') or confirmation!=queue_token(value):raise ValueError('La cola cambió. Revisá las órdenes pendientes nuevamente.')
            first=next((r for r in value['orders'] if r['status'] in OPEN),None)
            if first and first['status']!='pending':raise ValueError('Primero resolvé o cancelá la orden que requiere revisión.')
            if first:
                remote=self.snapshot()
                try:self.validate_pending(first,remote)
                except ValueError as exc:
                    first.update(status='conflict',message=str(exc));self.save(value);raise
            value['paused']=False;value['resumed_at']=self.clock().isoformat();self.save(value)
            return self.status()

    def enqueue(self, data, published):
        action = data.get('action')
        if action not in ('drive', 'cnrt', 'all', 'config', 'diagnostic','oneoff-set','oneoff-cancel','dictionary-save','history-import','history-review','history-recalculate'):
            raise ValueError('Acción no permitida.')
        expected = data.get('expected') or (published or {}).get('digest')
        if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
            raise ValueError('Primero consultá la configuración publicada. Se conserva el borrador local.')
        candidate = clean_config(data.get('config')) if action in ('config', 'diagnostic') else None
        if action=='config' and candidate and (published or {}).get('config'):
            from _ftr_runtime.config import validate_source_change
            validate_source_change(published['config'],candidate)
        extra = oneoff.command(data.get('oneoff'),self.clock(),action=='oneoff-cancel') if action in ('oneoff-set','oneoff-cancel') else None
        if candidate and len(encoded(candidate)) > 60000:
            raise ValueError('La configuración excede el límite de la solicitud.')
        from _ftr_runtime.statistics_commands import clean
        statistical=clean(action,data.get('statistical')) if action in ('dictionary-save','history-import','history-review','history-recalculate') else None
        dependency = data.get('depends_on')
        with self._lock, computer_lock(self.file('ordenes.lock')) as acquired:
            if not acquired:
                raise ValueError('Otra ventana está procesando órdenes. Reintentá en unos segundos.')
            value = self.read()
            if dependency:
                parent = next((r for r in value['orders'] if r['id'] == dependency), None)
                if not parent or parent['action'] != 'config' or parent['status'] in ('failed', 'cancelled', 'conflict','resolved'):
                    raise ValueError('La configuración de la que depende esta orden no está disponible.')
                expected = digest(parent['config'])
            fingerprint = hashlib.sha256(json.dumps([action, expected, candidate, dependency, extra, statistical], sort_keys=True).encode()).hexdigest()
            duplicate = next((r for r in value['orders'] if r['fingerprint'] == fingerprint and r['status'] in OPEN), None)
            if duplicate:
                return self.public(duplicate)
            if extra and any(r.get('oneoff',{}).get('source')==extra['source'] and r['status'] in OPEN for r in value['orders']):
                raise ValueError('Ya hay una orden pendiente para esta fuente. Esperá su resultado o cancelala antes del envío para cambiarla.')
            if sum(r['status'] in OPEN for r in value['orders']) >= 100:
                raise ValueError('Hay 100 órdenes pendientes. Revisalas antes de agregar otra.')
            row = dict(id=secrets.token_hex(16), action=action, expected=expected, config=candidate,
                       depends_on=dependency, fingerprint=fingerprint, status='pending',
                       created_at=self.clock().isoformat(), attempts=0, message=LABELS['pending'])
            if extra:row['oneoff']=extra
            if statistical:row['statistical']=statistical
            value['orders'].append(row)
            self.save(value)  # Se conserva ANTES de cualquier acceso a Internet.
            return self.public(row)

    def cancel(self, identifier):
        with self._lock, computer_lock(self.file('ordenes.lock')) as acquired:
            if not acquired:
                raise ValueError('La cola está ocupada. Reintentá la cancelación.')
            value = self.read()
            row = next((r for r in value['orders'] if r['id'] == identifier), None)
            if not row or row['status'] not in ('pending', 'authorization', 'conflict'):
                raise ValueError('Solo se puede cancelar una orden que todavía no se envió.')
            row.update(status='cancelled', message=LABELS['cancelled'])
            self.save(value)
            return self.public(row)

    def reconnected(self):
        with self._lock, computer_lock(self.file('ordenes.lock')) as acquired:
            if not acquired:
                return
            value = self.read()
            for row in value['orders']:
                if row['status'] == 'authorization':
                    row.update(status='pending', message=LABELS['pending'])
            self.save(value)

    def tick(self):
        if not self._lock.acquire(blocking=False):
            return
        try:
            with computer_lock(self.file('ordenes.lock')) as acquired:
                if not acquired:
                    return
                value = self.read()
                active = [r for r in value['orders'] if r['status'] in OPEN - {'conflict'}]
                if not active:
                    return  # Abrir el programa sin órdenes no consulta ni activa fuentes.
                for row in active:
                    if row['status'] == 'sending':
                        row.update(status='unknown', message=LABELS['unknown'])
                self.save(value)
                try:
                    remote = self.snapshot()
                    runs = self.runs(min((r['created_at'] for r in active),key=utc))
                except AuthorizationError:
                    for row in active:
                        if row['status'] in ('pending', 'authorization'):
                            row.update(status='authorization', message=LABELS['authorization'])
                    self.save(value)
                    return
                except Exception:
                    self.error = 'No se pudo consultar GitHub. Las órdenes siguen guardadas; no se confirma su publicación.'
                    return
                self.error = None
                for row in active:
                    self.reconcile(row,runs)
                self.save(value)
                if value.get('paused'):return
                # Serializa órdenes dependientes y no adelanta a una solicitud ambigua.
                row = next((r for r in value['orders'] if r['status'] in OPEN), None)
                if not row or row['status'] != 'pending':
                    return
                if row['action'] in ('oneoff-set','oneoff-cancel'):
                    try:
                        change=oneoff.command(row['oneoff'],self.clock(),row['action']=='oneoff-cancel',True)
                        if 'oneoffs' not in remote:raise ValueError('No se pudo consultar la programación extraordinaria publicada.')
                        actual=remote['oneoffs'].get('pending',{}).get(change['source'],{})
                        if actual.get('id')!=change['expected_id']:raise ValueError('La actualización programada cambió. Actualizá el estado y confirmá una nueva orden.')
                    except ValueError as exc:
                        row.update(status='conflict',message=str(exc));self.save(value);return
                if row.get('depends_on'):
                    parent = next(r for r in value['orders'] if r['id'] == row['depends_on'])
                    if parent['status'] != 'completed':
                        if parent['status'] in ('failed', 'cancelled', 'conflict','resolved'):
                            row.update(status='conflict', message='La configuración requerida no se publicó. Revisá esta orden.')
                            self.save(value)
                        return
                try:self.validate_pending(row,remote)
                except ValueError as exc:
                    row.update(status='conflict',message=str(exc));self.save(value);return
                if self.clock() - utc(row['created_at']) > timedelta(days=7):
                    row.update(status='conflict', message='La orden tiene más de siete días. Revisá y confirmá una nueva; no se ejecutan cambios antiguos automáticamente.')
                    self.save(value)
                    return
                if any(r['status'] in BUSY for r in runs):
                    return
                if row['attempts'] >= 3:
                    row.update(status='conflict', message='Tres envíos rechazados. Revisá la autorización y confirmá una nueva orden; no se seguirá reintentando.')
                    self.save(value)
                    return
                row.update(status='sending', attempts=row['attempts'] + 1, sent_at=self.clock().isoformat())
                self.save(value)
                try:
                    self.dispatch(row)
                except AuthorizationError:
                    # Rechazo HTTP explícito: no aceptado; reconectar no pierde la orden.
                    row.update(status='authorization', message=LABELS['authorization'])
                    row.setdefault('dispatch_evidence',[]).append(dict(at=self.clock().isoformat(),result='authorization_rejected'))
                except DispatchRejected as exc:
                    row.update(status='conflict',message=str(exc))
                    row.setdefault('dispatch_evidence',[]).append(dict(at=self.clock().isoformat(),result='rejected',http_status=exc.http_status))
                except Exception:
                    row.update(status='unknown', message=LABELS['unknown'])
                    row.setdefault('dispatch_evidence',[]).append(dict(at=self.clock().isoformat(),result='unconfirmed'))
                else:
                    row.update(status='sent', message=LABELS['sent'])
                    row.setdefault('dispatch_evidence',[]).append(dict(at=self.clock().isoformat(),result='accepted'))
                self.save(value)
        finally:
            self._lock.release()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        def run():
            while not self._stop.is_set():
                try:
                    self.tick()
                except Exception:
                    self.error = 'La cola necesita revisión. Se conservaron las órdenes y no se forzó ningún envío.'
                if self._stop.wait(60):
                    break
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
