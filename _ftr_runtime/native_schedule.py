"""Calendario nativo de GitHub, generado desde la configuración del panel.

La PC solo envía configuración. El cron queda en main, nunca en un reloj local.
El token adicional se usa únicamente al publicar cambios del archivo workflow.
"""
from __future__ import annotations

import base64
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import ZONE, clean_config

PATH = '.github/workflows/actualizar_parques.yml'
RECOVERY_PATH = '.github/workflows/ftr_recuperar_turnos.yml'
TOKEN_NAME = 'FTR_SCHEDULE_TOKEN'
REPO_URL = 'https://github.com/SanLean17/parque-movil-ftr.git'


def render_recovery() -> str:
    """Respaldo estable: comprueba pendientes, no agrega lecturas por cada evento."""
    return """name: FTR - Recuperar turnos pendientes
run-name: FTR · recovery · comprobación automática
on:
  schedule:
    - cron: '7,22,37,52 * * * *'
  workflow_dispatch:
permissions:
  contents: write
  pages: write
  actions: read
# Una comprobación sin trabajo no consulta fuentes ni escribe archivos.
# Solo el coordinador compartido posee el bloqueo de publicación.
jobs:
  comprobar:
    uses: ./.github/workflows/ftr_sincronizar.yml
    with:
      action: recovery
    secrets: inherit
"""


def render(config: dict) -> str:
    """cron diario a cada hora elegida; la agenda decide el intervalo de 1-60 días."""
    config = clean_config(config)
    crons = []
    notes = []
    # Argentina usa UTC-3. Se consulta zoneinfo en lugar de sumar una constante.
    # No se toma el año de los controles históricos como fecha del reloj.
    for key, label in (('drive', 'Planilla anual FTR'), ('cnrt', 'Parque móvil CNRT')):
        s = config[key]
        if s['enabled']:
            hour, minute = map(int, s['time'].split(':'))
            local = datetime(2026, 1, 1, hour, minute, tzinfo=ZoneInfo(ZONE))
            utc = local.astimezone(timezone.utc)
            expression = f'{utc.minute} {utc.hour} * * *'
            if expression not in crons:
                crons.append(expression)
            notes.append(f"# {label}: cada {s['days']} día(s), {s['time']} hs ({ZONE}).")
        else:
            notes.append(f'# {label}: programación desactivada; conserva actualización manual.')
    # Recuperación nocturna original: procesa solo turnos ya vencidos, no fuerza fuentes.
    if crons and '0 3 * * *' not in crons:
        crons.append('0 3 * * *')
    lines = [
        '# FTR-NATIVE-SCHEDULE-V1 — generado por _ftr_runtime/native_schedule.py',
        '# Horarios del panel reflejados en cron UTC. La PC puede estar apagada.',
        '# El intervalo de días se calcula en _ftr_runtime/agenda.py, no con */N del mes.',
        '# 03:00 UTC conserva una recuperación nocturna de turnos pendientes.',
        *notes,
        'name: Actualizar Parque Móvil FTR',
        "run-name: FTR · ${{ github.event_name == 'schedule' && 'schedule' || 'all' }} · ${{ github.event_name == 'schedule' && 'automático' || 'manual' }}",
        'on:',
    ]
    if crons:
        lines.append('  schedule:')
        lines.extend(f"    - cron: '{cron}'" for cron in crons)
    lines += [
        '  workflow_dispatch:',
        'permissions:',
        '  contents: write',
        '  pages: write',
        '  actions: read',
        '# Exclusión mutua solo en el workflow llamado, nunca también en este padre.',
        'jobs:',
        '  actualizar:',
        '    uses: ./.github/workflows/ftr_sincronizar.yml',
        '    with:',
        "      action: ${{ github.event_name == 'schedule' && 'scheduled' || 'all' }}",
        '    secrets: inherit',
        '',
    ]
    return '\n'.join(lines)


def changed(root: Path, config: dict) -> bool:
    file = Path(root) / PATH
    return not file.exists() or file.read_text(encoding='utf-8-sig') != render(config)


def authorization() -> str:
    token = os.environ.get(TOKEN_NAME, '').strip()
    if not token:
        raise ValueError(
            'No se guardaron los nuevos horarios: falta el secreto FTR_SCHEDULE_TOKEN '
            'en GitHub. Debe autorizar Contents: escritura y Workflows: escritura solo '
            'en parque-movil-ftr. El horario anterior se conserva. No envíes la clave por chat.'
        )
    if len(token) < 20 or len(token) > 300 or any(c.isspace() for c in token):
        raise ValueError('FTR_SCHEDULE_TOKEN no tiene un formato de autorización válido. No se modificó el calendario publicado.')
    return token


def preflight(root: Path, config: dict) -> None:
    """Rechaza cambios de calendario sin permiso ANTES de leer fuentes o cambiar datos."""
    if changed(root, config):
        authorization()


def stage(root: Path, config: dict) -> bool:
    """Añade solo el workflow generado a la misma transacción Git de configuración."""
    if not changed(root, config):
        return False
    authorization()
    file = Path(root) / PATH
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(render(config), encoding='utf-8', newline='\n')
    return True


def push(root: Path) -> None:
    """Usa el permiso de workflows sin persistirlo, imprimirlo ni ponerlo en argv."""
    token = authorization()
    header = 'AUTHORIZATION: basic ' + base64.b64encode(('x-access-token:' + token).encode()).decode()
    env = os.environ.copy()
    env['FTR_CALENDAR_GIT_AUTH'] = header
    args = [
        'git', '-c', 'credential.helper=',
        '-c', 'http.https://github.com/.extraheader=',
        '--config-env=http.https://github.com/.extraheader=FTR_CALENDAR_GIT_AUTH',
        'push', REPO_URL, 'HEAD:main',
    ]
    try:
        result = subprocess.run(args, cwd=root, env=env, text=True, capture_output=True,
                                encoding='utf-8', errors='replace', timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('No se pudo confirmar el guardado del calendario en GitHub. Revisá la ejecución antes de reintentar; no se fuerza una publicación.') from None
    if result.returncode:
        # Nunca interpolar stderr/stdout: podrían incluir credenciales o URLs de autenticación.
        raise ValueError(
            'GitHub rechazó el guardado conjunto de configuración y calendario. '
            'Revisá que FTR_SCHEDULE_TOKEN no haya vencido y tenga Contents y Workflows '
            'con escritura sobre este repositorio. Si otra operación cambió main, recargá '
            'la configuración y reintentá. No se usa force-push.'
        )
