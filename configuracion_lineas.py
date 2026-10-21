# ============================================================
# CONFIGURACIÓN OFICIAL DE LÍNEAS Y EMPRESAS CNRT
# ============================================================

from pathlib import Path
from _ftr_runtime.config import load, enabled

# Única referencia vigente: configuración publicada desde la aplicación.
LINEAS_EMPRESAS = enabled(load(Path(__file__).resolve().parent))


# Empresas únicas que hay que consultar en CNRT.
# Si una empresa tiene varias líneas, se consulta una sola vez.
EMPRESAS_CNRT = sorted(set(LINEAS_EMPRESAS.values()))


def empresa_de_linea(linea):
    """Devuelve el número de empresa CNRT correspondiente a una línea."""
    try:
        linea = int(linea)
    except (ValueError, TypeError):
        return None

    return LINEAS_EMPRESAS.get(linea)


def lineas_de_empresa(empresa):
    """Devuelve todas las líneas configuradas para una empresa."""
    try:
        empresa = int(empresa)
    except (ValueError, TypeError):
        return []

    return [
        linea
        for linea, empresa_configurada in LINEAS_EMPRESAS.items()
        if empresa_configurada == empresa
    ]
