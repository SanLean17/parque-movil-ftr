# ============================================================
# CONFIGURACIÓN OFICIAL DE LÍNEAS Y EMPRESAS CNRT
# ============================================================

LINEAS_EMPRESAS = {
    2: 2058,
    9: 2062,
    10: 2008,
    15: 67,
    17: 2024,
    22: 2022,
    24: 2005,
    29: 2064,
    32: 2048,
    33: 972,
    37: 2067,
    45: 2068,
    51: 2079,
    53: 2054,
    56: 2013,
    60: 2075,
    63: 2037,
    70: 2080,
    74: 2079,
    79: 2079,
    80: 2015,
    85: 359,
    91: 2013,
    92: 2023,
    95: 2003,
    98: 2021,
    100: 2042,
    113: 2037,
    119: 2068,
    126: 2119,
    128: 2048,
    129: 2033,
    133: 2010,
    134: 2042,
    135: 2013,
    148: 2033,
    154: 2068,
    158: 2048,
    159: 2100,
    160: 2101,
    164: 2062,
    168: 2105,
    177: 2079,
    178: 2111,
    179: 9085,
    180: 2099,
    195: 2077,
    197: 2033,
}


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
