"""Importación explícita del ZIP privado anterior; nunca ejecuta ni extrae archivos."""
import base64
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

LIMIT = 32 * 1024 * 1024


def import_archive(upload, directory, protect, previous, atomic):
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if upload is None:
        raise ValueError('Seleccioná el ZIP privado 06.3 original.')
    data = upload.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError('El ZIP supera el límite de 32 MB.')
    names = ('LLAVE_PRIVADA_DIAGNOSTICO.pem', 'resumen.json', 'detalle_admin.enc.json')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            selected = {}
            for name in names:
                matches = [x for x in archive.infolist() if PurePosixPath(x.filename).name == name]
                if len(matches) != 1 or matches[0].file_size > 2 * 1024 * 1024:
                    raise ValueError('El ZIP no contiene una copia única y válida de los informes 06.3.')
                selected[name] = archive.read(matches[0])
        raw_key = selected[names[0]]
        if len(raw_key) > 10000:
            raise ValueError('La llave de informes supera el tamaño permitido.')
        key = serialization.load_pem_private_key(raw_key, password=None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise ValueError('La llave de informes no es válida.')
        report = json.loads(selected[names[1]])
        envelope = json.loads(selected[names[2]])
        if envelope.get('format') != 'FTR-DIAGNOSTICO-3':
            raise ValueError('El detalle tiene un formato distinto.')
        b = lambda field: base64.b64decode(envelope[field], validate=True)
        symmetric = key.decrypt(b('wrapped_key'), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        detail = json.loads(AESGCM(symmetric).decrypt(b('nonce'), b('ciphertext'), b'FTR-DIAGNOSTICO-3'))
        identity = (report.get('periodo'), report.get('revision_repositorio'), report.get('inicio_lectura_utc'))
        if (not all(identity) or identity != (detail.get('periodo'), detail.get('revision_repositorio'), detail.get('detectado_utc'))
            or report.get('modo') != 'DIAGNOSTICO_SIN_PUBLICAR' or detail.get('version') != 3
            or not isinstance(report.get('lineas'), list) or not isinstance(detail.get('incidencias'), list)):
            raise ValueError('El resumen y el detalle no pertenecen a una misma lectura válida.')
        moment = datetime.fromisoformat(report['inicio_lectura_utc'])
        if moment.tzinfo is None:
            raise ValueError('La lectura no tiene fecha completa.')
    except Exception:
        raise ValueError('No se pudo validar el ZIP 06.3, su llave y sus informes. Se conservaron todos los archivos anteriores.') from None
    root = Path(directory)
    protected = root / 'diagnostico.dpapi'
    old_pem = root / 'LLAVE_PRIVADA_DIAGNOSTICO.pem'
    if protected.exists() or old_pem.exists():
        existing = protect(protected.read_bytes(), True) if protected.exists() else old_pem.read_bytes()
        old_key = serialization.load_pem_private_key(existing, password=None)
        if old_key.public_key().public_numbers() != key.public_key().public_numbers():
            raise ValueError('Este equipo ya conserva otra llave de informes. No se reemplazó ni se invalidó ningún informe.')
    cached = previous()
    replace = not cached or not cached.get('report')
    if not replace:
        try:
            replace = datetime.fromisoformat(cached['report']['inicio_lectura_utc']) < moment
        except (KeyError, TypeError, ValueError):
            # Un informe de antigüedad desconocida tampoco se pisa silenciosamente.
            replace = False
    # Preparar ambos cifrados antes de escribir. DPAPI vincula al usuario Windows.
    protected_key = protect(raw_key)
    result = dict(report=report, details=detail, run_id=None)
    protected_report = protect(json.dumps(result, ensure_ascii=False).encode()) if replace else None
    if not protected.exists():
        atomic(protected, protected_key)
    if replace:
        atomic(root / 'informe.dpapi', protected_report)
    return dict(ok=True, diagnostic=result if replace else cached,
                message='Llave anterior recuperada y protegida en este equipo. ' +
                ('Informe 06.3 recuperado con su fecha original.' if replace else 'Se conservó el informe local más reciente.'))
