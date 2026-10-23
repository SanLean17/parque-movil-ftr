"""Administración local FTR. Solo loopback; no distribuye la clave de Google.
El token de GitHub se protege con DPAPI en Windows. Nunca se incorpora al HTML.
"""
from __future__ import annotations
import base64
import io
import json
import logging
import os
import secrets
import sys
import tempfile
import threading
import webbrowser
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# PyInstaller --noconsole no proporciona stdout/stderr en Windows.
for stream in ('stdout', 'stderr'):
    if getattr(sys, stream) is None:
        setattr(sys, stream, open(os.devnull, 'w', encoding='utf-8'))

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests
from flask import Flask, abort, jsonify, make_response, request
from werkzeug.serving import make_server
from _ftr_runtime.config import clean_config,digest,encoded
from _ftr_app.outbox import AuthorizationError
from _ftr_app.local_clock import write_json

REPO='SanLean17/parque-movil-ftr'
WORKFLOW='ftr_sincronizar.yml'
BASE='https://api.github.com/repos/'+REPO+'/'
VERSION='06.1'
PORT=58641
SESSION=secrets.token_urlsafe(40)
BOOT=secrets.token_urlsafe(32)
CSRF=secrets.token_urlsafe(40)
# Las cookies no se separan por puerto: cada instancia tiene un nombre propio.
COOKIE_NAME='ftr_'+secrets.token_hex(8)
ORIGIN=f'http://127.0.0.1:{PORT}'
DATA=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'FTR_Administracion'
DATA.mkdir(parents=True,exist_ok=True)
BUNDLE=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
RESOURCE=BUNDLE
app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=32*1024*1024
logging.getLogger('werkzeug').disabled=True
_lock=threading.Lock()
_token=None


def protect(data,decrypt=False):
    if os.name!='nt':raise ValueError('El guardado seguro de credenciales requiere Windows.')
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data)
    original=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    output=Blob()
    function=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not function(ctypes.byref(original),None,None,None,None,1,ctypes.byref(output)):
        raise ValueError('Windows no pudo proteger la credencial. No se guardó en texto plano.')
    try:return ctypes.string_at(output.pbData,output.cbData)
    finally:
        free=ctypes.windll.kernel32.LocalFree
        free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p
        free(ctypes.cast(output.pbData,ctypes.c_void_p))


def token():
    global _token
    if _token is None and os.name=='nt' and (DATA/'github.dpapi').exists():
        try:_token=protect((DATA/'github.dpapi').read_bytes(),True).decode()
        except Exception:raise AuthorizationError('No se pudo abrir la autorización de este equipo. Conectá GitHub de nuevo.') from None
    if not _token:raise AuthorizationError('Conectá GitHub en la sección Conexiones de este equipo.')
    return _token


def api(method,suffix,payload=None,auth=None):
    if '--self-test' in sys.argv or '--browser-test' in sys.argv:
        raise ValueError('Prueba aislada: conexión externa deshabilitada.')
    # No se acepta una URL del cliente. La autorización solo se envía a este repositorio.
    r=requests.request(method,BASE+suffix if suffix else BASE.rstrip('/'),headers={'Authorization':'Bearer '+(auth or token()),'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},json=payload,timeout=(8,50),allow_redirects=False)
    if r.status_code==401:raise AuthorizationError('GitHub rechazó la autorización. Puede haber vencido; reconectá este equipo.')
    if r.status_code==403:raise AuthorizationError('GitHub no permitió la operación. Revisá Actions con lectura y escritura y acceso a este repositorio.')
    if r.status_code==404:raise ValueError('GitHub no encontró el recurso autorizado. Revisá el repositorio y que la integración esté activada.')
    if not r.ok:raise ValueError('No se completó la operación con GitHub (HTTP '+str(r.status_code)+'). Revisá su estado antes de repetirla.')
    return r.json() if r.content else {}


def json_file(name):
    value=api('GET','contents/'+name+'?ref=main')
    return json.loads(base64.b64decode(value['content']))


def remote():
    c=clean_config(json_file('_ftr_config.json'))
    result={'config':c,'digest':digest(c)}
    (DATA/'config_remota.json').write_text(json.dumps(result),encoding='utf-8')
    return result


def cached(name,default):
    try:return json.loads((DATA/name).read_text(encoding='utf-8'))
    except (OSError,ValueError):return default


def atomic_bytes(path, data):
    temporary=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
    try:
        with temporary.open('wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def diagnostic_cache():
    protected=DATA/'informe.dpapi'
    if protected.exists():
        try:return json.loads(protect(protected.read_bytes(),True))
        except Exception:raise ValueError('No se pudo abrir el informe protegido de este usuario de Windows. Los archivos se conservaron.') from None
    return cached('informe.json',None)


def last_runs():
    rows=api('GET','actions/workflows/'+WORKFLOW+'/runs?per_page=6').get('workflow_runs',[])
    return [{'id':r['id'],'title':r.get('display_title',r.get('name','Actualización')),'status':r['status'],'conclusion':r.get('conclusion'),'url':r['html_url'],'created_at':r['created_at']} for r in rows]


def unseal(value):
    from cryptography.hazmat.primitives import serialization,hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if value.get('format')!='FTR-DIAGNOSTICO-3':raise ValueError('El informe cifrado tiene un formato no reconocido.')
    protected=DATA/'diagnostico.dpapi'
    if protected.exists():
        raw_key=protect(protected.read_bytes(),True)
    else:
        key_path=DATA/'LLAVE_PRIVADA_DIAGNOSTICO.pem'
        if not key_path.exists():key_path=BUNDLE/'LLAVE_PRIVADA_DIAGNOSTICO.pem'
        if not key_path.exists():return None
        raw_key=key_path.read_bytes()
    key=serialization.load_pem_private_key(raw_key,password=None)
    b=lambda field:base64.b64decode(value[field],validate=True)
    symmetric=key.decrypt(b('wrapped_key'),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    detail=json.loads(AESGCM(symmetric).decrypt(b('nonce'),b('ciphertext'),b'FTR-DIAGNOSTICO-3'))
    if os.name=='nt' and not protected.exists():
        atomic_bytes(protected,protect(raw_key))
    # Conserva el original por compatibilidad; jamás rota ni distribuye la clave.
    return detail


def report_for_run(run_id):
    if type(run_id) is not int or run_id<=0:raise ValueError('La ejecución no es válida.')
    items=api('GET',f'actions/runs/{run_id}/artifacts?per_page=100').get('artifacts',[])
    artifact=next((x for x in items if x['name']=='ftr-informe-administrativo' and not x.get('expired')),None)
    if not artifact:return None
    response=requests.get(BASE+f"actions/artifacts/{artifact['id']}/zip",headers={'Authorization':'Bearer '+token(),'Accept':'application/vnd.github+json'},timeout=30,allow_redirects=False)
    if response.status_code!=302:raise ValueError('El informe todavía no está disponible para descargar.')
    location=response.headers.get('Location','')
    if urlparse(location).scheme!='https':raise ValueError('La descarga del informe no tiene una dirección segura.')
    # La URL firmada no recibe el token de GitHub y no se registra ni se guarda.
    r=requests.get(location,timeout=60,stream=True)
    r.raise_for_status()
    data=bytearray()
    for chunk in r.iter_content(65536):
        data.extend(chunk)
        if len(data)>25000000:raise ValueError('El informe supera el tamaño permitido.')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if sum(i.file_size for i in z.infolist())>50000000:raise ValueError('El informe descomprimido es demasiado grande.')
        report=json.loads(z.read('resumen.json')) if 'resumen.json' in z.namelist() else None
        detail=unseal(json.loads(z.read('detalle_admin.enc.json'))) if 'detalle_admin.enc.json' in z.namelist() else None
        error=json.loads(z.read('operacion.json')) if 'operacion.json' in z.namelist() else None
    if report and detail and (report.get('periodo'),report.get('revision_repositorio'),report.get('inicio_lectura_utc'))!=(detail.get('periodo'),detail.get('revision_repositorio'),detail.get('detectado_utc')):
        raise ValueError('El detalle y el resumen corresponden a ejecuciones distintas.')
    result={'report':report,'details':detail,'operation':error,'run_id':run_id}
    # Un recibo de error sin informe no reemplaza la última lectura válida local.
    if report:
        if os.name=='nt':atomic_bytes(DATA/(f"historico-{report['periodo']}.dpapi" if report.get('historico') else 'informe.dpapi'),protect(json.dumps(result,ensure_ascii=False).encode()))
        else:write_json(DATA/(f"historico-{report['periodo']}.json" if report.get('historico') else 'informe.json'),result)
    return result


def matches(value, expected):
    return isinstance(value,str) and value.isascii() and secrets.compare_digest(value,expected)


@app.before_request
def secure():
    if request.host!=f'127.0.0.1:{PORT}':abort(403)
    if request.path!='/api/import-legacy' and (request.content_length or 0)>2*1024*1024:abort(413)
    if request.path=='/iniciar/'+BOOT:
        if request.method!='GET':abort(405)
        if request.headers.get('Origin') not in (None,ORIGIN):abort(403)
        if request.headers.get('Sec-Fetch-Site')=='cross-site':abort(403)
        return
    if not matches(request.cookies.get(COOKIE_NAME,''),SESSION):abort(403)
    if request.path.startswith('/api/'):
        if not matches(request.headers.get('X-FTR-CSRF',''),CSRF):abort(403)
        if request.method!='GET' and request.headers.get('Origin')!=ORIGIN:abort(403)


@app.after_request
def headers(response):
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


@app.errorhandler(Exception)
def errors(exc):
    from werkzeug.exceptions import HTTPException
    if isinstance(exc,HTTPException):
        messages={403:'El enlace de inicio o la sesión de este panel no es válido. Cerrá esta pestaña y abrí FTR_Administracion.exe desde la carpeta extraída.',
                  404:'No se encontró esta pantalla del panel. Abrí el programa desde la carpeta extraída, no desde un enlace anterior.',
                  405:'Esta operación no está permitida desde ese enlace. Utilizá los botones del panel.',
                  413:'El archivo o la solicitud supera el tamaño permitido.'}
        message=messages.get(exc.code,'La solicitud no se pudo procesar. Volvé a abrir el programa.')
        if not request.path.startswith('/api/') and 'text/html' in request.headers.get('Accept',''):
            from html import escape
            response=make_response('<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Administración FTR — Inicio</title><body style="font:16px system-ui;max-width:620px;margin:12vh auto;padding:24px;line-height:1.6"><h1>No se pudo abrir el panel</h1><p>'+escape(message)+'</p><p>Esto corresponde al inicio local; no cambies los permisos de Google Drive ni de GitHub.</p><small>Referencia: inicio local '+str(exc.code)+'</small></body></html>',exc.code)
            response.headers['Content-Type']='text/html; charset=utf-8'
            return response
        return jsonify(error=message,code=exc.code),exc.code
    if isinstance(exc,AuthorizationError):return jsonify(error=str(exc),code='authorization'),401
    if isinstance(exc,ValueError):return jsonify(error=str(exc)),400
    if isinstance(exc,requests.RequestException):return jsonify(error='No se pudo conectar a GitHub. El borrador sigue en tu equipo; revisá Internet y reintentá.'),503
    return jsonify(error='No se completó la operación. Revisá la última ejecución antes de repetirla.'),500


@app.get('/iniciar/<bootstrap>')
def start(bootstrap):
    if not matches(bootstrap,BOOT):abort(403)
    response=make_response('',302);response.headers['Location']='/'
    response.set_cookie(COOKIE_NAME,SESSION,httponly=True,samesite='Strict',path='/')
    return response


@app.get('/')
def index():
    return (RESOURCE/'panel.html').read_text(encoding='utf-8').replace('__FTR_CSRF__',CSRF)


@app.get('/panel-bridge.js')
def panel_bridge():
    response=make_response((RESOURCE/'panel-bridge.js').read_text(encoding='utf-8'))
    response.headers['Content-Type']='text/javascript; charset=utf-8'
    return response


@app.get('/ftr-historial.js')
@app.get('/panel-history.js')
def history_resources():
    name=request.path[1:]
    path=RESOURCE/name
    if name=='ftr-historial.js' and not getattr(sys,'frozen',False):
        path=Path(__file__).resolve().parents[1]/name
    response=make_response(path.read_text(encoding='utf-8'))
    response.headers['Content-Type']='text/javascript; charset=utf-8'
    return response


@app.get('/api/bootstrap')
def bootstrap():
    connected=True
    try:token()
    except ValueError:connected=False
    diag=diagnostic_cache()
    if diag is None and (BUNDLE/'resumen.json').exists():
        summary=json.loads((BUNDLE/'resumen.json').read_text(encoding='utf-8'))
        detail=unseal(json.loads((BUNDLE/'detalle_admin.enc.json').read_text(encoding='utf-8'))) if (BUNDLE/'detalle_admin.enc.json').exists() else None
        diag={'report':summary,'details':detail,'run_id':None}
    return jsonify(version=VERSION,connected=connected,draft=cached('borrador.json',None),remote=cached('config_remota.json',None),diagnostic=diag,preferences=cached('preferencias.json',{}))


@app.post('/api/preferences')
def preferences():
    value=request.get_json()
    if not isinstance(value,dict) or value.get('theme') not in ('light','dark'):
        raise ValueError('La preferencia visual no es válida.')
    write_json(DATA/'preferencias.json',{'theme':value['theme']})
    return jsonify(ok=True)


@app.post('/api/import-legacy')
def import_legacy():
    from _ftr_app.migration import import_archive
    return jsonify(import_archive(request.files.get('archive'),DATA,protect,diagnostic_cache,atomic_bytes))


@app.post('/api/draft')
def draft():
    content=request.get_json()
    c=clean_config(content['config'])
    value={'config':c,'expected':content.get('expected'),'saved_at':datetime.now(timezone.utc).isoformat()}
    write_json(DATA/'borrador.json',value)
    return jsonify(ok=True)


@app.post('/api/reset-draft')
def reset_draft():
    (DATA/'borrador.json').unlink(missing_ok=True)
    return jsonify(ok=True)


@app.post('/api/connect')
def connect():
    global _token
    value=request.get_json().get('token','').strip()
    if not 20<=len(value)<=300 or any(c.isspace() for c in value):raise ValueError('La autorización de GitHub no tiene el formato esperado.')
    info=api('GET','actions/workflows/'+WORKFLOW,auth=value)
    if not info.get('id'):raise ValueError('No se encontró la automatización FTR.')
    with _lock:
        if os.name=='nt':atomic_bytes(DATA/'github.dpapi',protect(value.encode()))
        _token=value
    return jsonify(ok=True,persistent=os.name=='nt')


@app.post('/api/disconnect')
def disconnect():
    global _token
    with _lock:
        _token=None
        (DATA/'github.dpapi').unlink(missing_ok=True)
    return jsonify(ok=True)


@app.get('/api/status')
def status():
    result=remote()
    try:result['state']=json_file('_ftr_estado.json')
    except ValueError:result['state']={}
    result['runs']=last_runs()
    return jsonify(result)


@app.post('/api/submit')
def submit():
    data=request.get_json();action=data.get('action')
    if action not in ('drive','cnrt','all','config','diagnostic'):raise ValueError('Acción no permitida.')
    with _lock:
        r=remote();jobs=last_runs()
        if any(x['status'] in ('queued','in_progress','waiting','pending') for x in jobs):
            raise ValueError('Ya hay una actualización en espera o en ejecución. Esperá a que termine para no duplicarla.')
        cfg='';expected=''
        if action in ('config','diagnostic'):
            candidate=clean_config(data.get('config'));cfg=encoded(candidate).decode()
            if len(cfg.encode())>60000:raise ValueError('La configuración excede el límite de la solicitud.')
            if action=='config':
                if data.get('expected')!=r['digest']:raise ValueError('Otra computadora publicó una configuración diferente. Recargá la configuración y revisá tu borrador.')
                expected=r['digest']
        identifier=secrets.token_hex(8)
        api('POST','actions/workflows/'+WORKFLOW+'/dispatches',{'ref':'main','inputs':{'action':action,'config_json':cfg,'expected':expected,'request_id':identifier}})
    return jsonify(ok=True,request_id=identifier,message='Solicitud enviada. Falta que GitHub ejecute y publique el resultado.')


@app.post('/api/report')
def report():return jsonify(report_for_run(request.get_json().get('run_id')))


@app.post('/api/quit')
def quit_panel():
    callback=app.config.get('SHUTDOWN')
    if callback:threading.Timer(0.3,callback).start()
    return jsonify(ok=True)


def check_resources():
    path=RESOURCE/'panel.html'
    if not path.is_file():
        raise ValueError('Falta panel.html junto al programa. Cerrá el ZIP, elegí Extraer todo y abrí FTR_Administracion.exe dentro de la carpeta extraída. Conservá todos los archivos juntos.')
    if '__FTR_CSRF__' not in path.read_text(encoding='utf-8-sig'):
        raise ValueError('La plantilla del panel no corresponde a este programa. Extraé el paquete completo en una carpeta nueva, sin mezclar versiones.')
    version=tuple(map(int,VERSION.split('.')))
    if version >= (6,3,1) and not (RESOURCE/'panel-bridge.js').is_file():
        raise ValueError('Falta panel-bridge.js junto al programa. Extraé todo el paquete '+VERSION+' en una carpeta nueva.')
    if version >= (6,3,5) and not (RESOURCE/'panel-statistics-admin.js').is_file():
        raise ValueError('Falta el diccionario técnico. Extraé el paquete completo en una carpeta nueva.')
    if version >= (6,3,2):
        for name in ('panel-history.js','ftr-historial.js'):
            path=RESOURCE/name
            if name=='ftr-historial.js' and not getattr(sys,'frozen',False):path=Path(__file__).resolve().parents[1]/name
            if not path.is_file():raise ValueError('Falta '+name+'. Extraé todo el paquete '+VERSION+' en una carpeta nueva.')


def local_server():
    global PORT,ORIGIN
    # El SO asigna un puerto libre: una instancia anterior no atiende este inicio.
    srv=make_server('127.0.0.1',0,app,threaded=True)
    PORT=srv.server_port
    ORIGIN=f'http://127.0.0.1:{PORT}'
    app.config['SHUTDOWN']=srv.shutdown
    thread=threading.Thread(target=srv.serve_forever,daemon=True)
    thread.start()
    return srv,thread


def verify_local_http():
    # Solo loopback, sin proxies del equipo, sin token GitHub ni acceso a Google.
    with requests.Session() as client:
        client.trust_env=False
        r=client.get(ORIGIN+'/iniciar/'+BOOT,timeout=8,allow_redirects=False)
        if r.status_code!=302 or not client.cookies.get(COOKIE_NAME):
            raise ValueError('No se pudo iniciar la sesión local del panel. Cerrá las ventanas anteriores y volvé a abrir el programa extraído.')
        r=client.get(ORIGIN+'/',timeout=8)
        if r.status_code!=200 or '__FTR_CSRF__' in r.text:
            raise ValueError('El panel no pudo cargar sus archivos. Extraé el paquete completo en una carpeta nueva.')


def notify_start_error(message):
    if os.name=='nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,message,'Administración FTR — Inicio',0x10)
    else:print(message,file=sys.stderr)


def main():
    global DATA,BUNDLE,_token
    testing='--self-test' in sys.argv or '--browser-test' in sys.argv
    test_dir=tempfile.TemporaryDirectory(prefix='ftr-inicio-test-') if testing else None
    if test_dir:
        DATA=Path(test_dir.name);_token=None
        if '--browser-test' in sys.argv:
            # Perfil ficticio persistente, adyacente al intercambio de la prueba.
            # Nunca utiliza LOCALAPPDATA ni inicia la cola de salida.
            target=Path(sys.argv[sys.argv.index('--browser-test')+1]).resolve()
            DATA=target.parent/'perfil-prueba'
            DATA.mkdir(parents=True,exist_ok=True)
    srv=None;thread=None
    try:
        check_resources()
        srv,thread=local_server()
        verify_local_http()
        if '--self-test' in sys.argv:
            if os.name=='nt':
                sample=b'FTR_PRUEBA_SIN_CREDENCIAL'
                assert protect(protect(sample),True)==sample
            (RESOURCE/'self-test-ok.txt').write_text(VERSION+': recursos, sesión, redirección y HTML sobre HTTP loopback; DPAPI Windows: OK. Sin conexión a GitHub o Google.',encoding='utf-8')
            return
        if '--browser-test' in sys.argv:
            # Intercambio local exclusivo de CI; nunca se sube ni imprime este archivo.
            target=Path(sys.argv[sys.argv.index('--browser-test')+1])
            target.write_text(json.dumps({'url':ORIGIN+'/iniciar/'+BOOT,'version':VERSION}),encoding='utf-8')
            timeout=threading.Timer(300,srv.shutdown)
            timeout.daemon=True
            timeout.start()
        else:
            webbrowser.open(ORIGIN+'/iniciar/'+BOOT)
        thread.join()
    except Exception as exc:
        message=str(exc) if isinstance(exc,ValueError) else 'No se pudo iniciar el servidor local. Extraé todo el paquete, cerrá el panel anterior y volvé a abrir FTR_Administracion.exe.'
        if testing:
            (RESOURCE/'self-test-error.txt').write_text(message,encoding='utf-8')
            raise SystemExit(1) from None
        notify_start_error(message)
    finally:
        if srv:
            srv.shutdown();srv.server_close()
        if thread:thread.join(timeout=3)
        if test_dir:test_dir.cleanup()


if __name__=='__main__':main()
