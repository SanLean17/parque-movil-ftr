"""Prueba de autorización real, exclusivamente en la rama de pruebas.

Solo modifica un comentario del workflow de calendario EN ESTA RAMA y luego
restaura sus bytes. No ejecuta workflows de producción, no escribe main, no
consulta Google/CNRT, no muestra tokens y no los almacena en el repositorio.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

REPO = 'SanLean17/parque-movil-ftr'
BRANCH = 'ftr/calendario-nativo'
FILE = '.github/workflows/actualizar_parques.yml'
BASE = 'https://api.github.com/repos/' + REPO + '/'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main() -> int:
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != 'refs/heads/' + BRANCH:
        print('Prueba cancelada: solo está autorizada en la rama de verificación.')
        return 1
    token = os.environ.get('FTR_SCHEDULE_TOKEN', '').strip()
    if not token:
        print('FTR_SCHEDULE_TOKEN no está disponible en esta ejecución. No se hizo ninguna escritura.')
        return 1
    if not 20 <= len(token) <= 300 or any(c.isspace() for c in token):
        print('La credencial tiene un formato no válido. No se hizo ninguna escritura.')
        return 1
    run = os.environ.get('GITHUB_RUN_ID', '')
    attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '')
    if not re.fullmatch(r'\d+', run) or not re.fullmatch(r'\d+', attempt):
        print('Falta identificación de la prueba. Sin escritura.')
        return 1
    opener = build_opener(NoRedirect())

    def api(method, suffix, payload=None):
        # Destino fijo: nunca se toma una URL ni una rama de datos externos.
        req = Request(BASE + suffix,
                      data=json.dumps(payload).encode('utf-8') if payload is not None else None,
                      method=method,
                      headers={'Authorization': 'Bearer ' + token,
                               'Accept': 'application/vnd.github+json',
                               'Content-Type': 'application/json',
                               'X-GitHub-Api-Version': '2022-11-28',
                               'User-Agent': 'FTR-calendar-permission-check'})
        try:
            with opener.open(req, timeout=30) as response:
                raw = response.read(2000000)
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            # Nunca imprimir el cuerpo, las cabeceras o la URL de una respuesta.
            raise ValueError(f'GitHub rechazó {method} durante la prueba (HTTP {exc.code}).') from None
        except (URLError, TimeoutError, OSError, json.JSONDecodeError):
            raise ValueError('No se pudo confirmar la respuesta de GitHub. Revisar el resultado antes de repetir.') from None

    def fetch_file():
        value = api('GET', 'contents/' + FILE + '?' + urlencode({'ref': BRANCH}))
        if value.get('encoding') != 'base64' or value.get('path') != FILE:
            raise ValueError('Respuesta del archivo de pruebas inesperada.')
        return value, base64.b64decode(value['content'])

    def write_file(content, sha, message):
        return api('PUT', 'contents/' + FILE,
                   {'branch': BRANCH, 'sha': sha, 'message': message,
                    'content': base64.b64encode(content).decode('ascii')})

    error = None
    original = modified = None
    main_before = None
    restored = False
    write_attempted = False
    report = {'secret_available': True, 'workflow_write_verified': False,
              'restored': False, 'production_dispatches': 0, 'sources_read': False}
    try:
        main_before = api('GET', 'git/ref/heads/main')['object']['sha']
        metadata, original = fetch_file()
        modified = original + f'\n# Verificación reversible de permiso {run}-{attempt}; solo rama de pruebas.\n'.encode('utf-8')
        write_attempted = True
        written = write_file(modified, metadata['sha'], 'Verificar permiso Workflows solo en rama de pruebas')
        if not written.get('content', {}).get('sha'):
            raise ValueError('GitHub no confirmó la escritura de prueba.')
        report['workflow_write_verified'] = True
    except ValueError as exc:
        error = str(exc)
    except Exception as exc:
        error = 'La prueba no se completó (' + type(exc).__name__ + ').'
    finally:
        if write_attempted:
            try:
                current, content = fetch_file()
                if content == modified:
                    write_file(original, current['sha'], 'Restaurar exactamente el calendario de la rama de pruebas')
                    _, content = fetch_file()
                if content != original:
                    raise ValueError('La rama de pruebas cambió durante la verificación. No se sobrescribió contenido ajeno.')
                restored = True
            except Exception:
                error = 'No se confirmó la restauración de la rama de pruebas. main no fue destino de ninguna escritura.'
        report['restored'] = restored
    try:
        after = api('GET', 'git/ref/heads/main')['object']['sha']
        report['main_unchanged_during_check'] = main_before is not None and main_before == after
        report['main_revision'] = after
    except Exception:
        report['main_unchanged_during_check'] = None
    report['status'] = 'verified' if error is None and report['workflow_write_verified'] and restored else 'error'
    if error:
        report['error'] = error
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write('## Permiso de calendario — prueba sin fuentes\n\n```json\n' + text + '\n```\n')
    return 0 if report['status'] == 'verified' else 1


if __name__ == '__main__':
    sys.exit(main())
