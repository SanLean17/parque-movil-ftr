"""Almacén particular del usuario Windows, independiente del instalador/año."""
import json
from _ftr_runtime.mechanical_review import fingerprint

class Store:
    def __init__(self,server):self.server=server
    @property
    def path(self):return self.server.DATA/'interpretaciones.dpapi'
    def read(self):
        if not self.path.exists():return dict(version=1,revision=0,registros={})
        try:
            value=json.loads(self.server.protect(self.path.read_bytes(),True))
            if set(value)!={'version','revision','registros'} or value['version']!=1 or not isinstance(value['registros'],dict):raise ValueError()
            return value
        except Exception:raise ValueError('No se pudo abrir el archivo protegido de interpretaciones. Se conservó intacto.') from None
    def save(self,correction,expected):
        with self.server._lock:
            current=self.read()
            if fingerprint(current)!=expected:raise ValueError('Las interpretaciones cambiaron. Calculá nuevamente la vista previa.')
            current['registros'][correction['registro_id']]=correction;current['revision']+=1
            body=json.dumps(current,ensure_ascii=False).encode()
            # Sin alternativa en texto plano, tampoco si falla DPAPI.
            self.server.atomic_bytes(self.path,self.server.protect(body))
            return current
