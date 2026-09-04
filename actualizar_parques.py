# ============================================================
# ACTUALIZADOR DE PARQUES - PARQUE MÓVIL FTR
# ============================================================

from pathlib import Path
import re

import pandas as pd

from configuracion_lineas import LINEAS_EMPRESAS


# ============================================================
# CONFIGURACIÓN
# ============================================================

CARPETA_CNRT = Path("cnrt")
CARPETA_PARQUES = Path("parques")


# ============================================================
# NORMALIZAR NOMBRES DE COLUMNAS
# ============================================================

def normalizar_nombre_columna(nombre):
    return (
        str(nombre)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def buscar_columna(df, posibles):

    mapa = {}

    for columna in df.columns:

        normalizada = normalizar_nombre_columna(
            columna
        )

        mapa[normalizada] = columna

    for posible in posibles:

        normalizada = normalizar_nombre_columna(
            posible
        )

        if normalizada in mapa:

            return mapa[normalizada]

    return None


# ============================================================
# NORMALIZAR EMPRESA
# ============================================================

def normalizar_empresa(valor):

    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    # Evita casos como 2077.0
    if re.fullmatch(r"\d+\.0", texto):
        texto = texto[:-2]

    return texto


# ============================================================
# EXTRAER NÚMEROS DE LÍNEA
# ============================================================

def extraer_lineas(valor):

    """
    Convierte un campo CNRT como:

        195

    o:

        195, 2077IE, 2077OE, 2077OP1, 2077OP11

    en:

        {195, 2077}

    Pero NO utilizaremos todos los números encontrados
    automáticamente. La comparación final se hace contra
    LINEAS_EMPRESAS.

    Esto permite detectar correctamente 195 aunque el campo
    contenga información adicional.
    """

    if pd.isna(valor):
        return set()

    texto = str(valor).strip()

    if not texto:
        return set()

    encontrados = set()

    # --------------------------------------------------------
    # Separar los diferentes elementos del campo
    # --------------------------------------------------------

    partes = re.split(
        r"[,;/|]+",
        texto
    )

    for parte in partes:

        parte = parte.strip()

        if not parte:
            continue

        # ----------------------------------------------------
        # Tomar solamente el número inicial
        #
        # Ejemplos:
        #
        # 195       -> 195
        # 2077IE    -> 2077
        # 2077OP1   -> 2077
        # 2077OP11  -> 2077
        # ----------------------------------------------------

        coincidencia = re.match(
            r"^(\d+)",
            parte
        )

        if coincidencia:

            numero = coincidencia.group(1)

            encontrados.add(
                numero
            )

    return encontrados


# ============================================================
# DETERMINAR SI UNA FILA PERTENECE A UNA LÍNEA
# ============================================================

def pertenece_a_linea(
    valor_linea,
    linea_buscada
):

    linea_buscada = str(
        linea_buscada
    ).strip()

    if not linea_buscada:
        return False

    lineas_encontradas = extraer_lineas(
        valor_linea
    )

    return linea_buscada in lineas_encontradas


# ============================================================
# LEER CSV CNRT
# ============================================================

def leer_csv_cnrt(ruta):

    print()
    print(
        f"Leyendo: {ruta}"
    )

    # --------------------------------------------------------
    # Primero intentamos UTF-8
    # --------------------------------------------------------

    try:

        df = pd.read_csv(
            ruta,
            dtype=str,
            encoding="utf-8-sig"
        )

    except Exception:

        # ----------------------------------------------------
        # Segundo intento: latin-1
        # ----------------------------------------------------

        df = pd.read_csv(
            ruta,
            dtype=str,
            encoding="latin-1"
        )

    # --------------------------------------------------------
    # Limpiar nombres de columnas
    # --------------------------------------------------------

    df.columns = [
        str(columna).strip()
        for columna in df.columns
    ]

    print(
        f"Filas encontradas: {len(df)}"
    )

    print(
        "Columnas:"
    )

    print(
        list(df.columns)
    )

    return df


# ============================================================
# FILTRAR UNA LÍNEA
# ============================================================

def filtrar_por_linea(
    df,
    linea,
    empresa_esperada,
    nombre_archivo
):

    columna_linea = buscar_columna(
        df,
        [
            "linea",
            "lineanro",
            "nrolinea",
            "linea_nro"
        ]
    )

    if columna_linea is None:

        print(
            f"ADVERTENCIA: {nombre_archivo} "
            "no tiene columna 'linea'."
        )

        return pd.DataFrame(
            columns=df.columns
        )

    columna_empresa = buscar_columna(
        df,
        [
            "empresaNro",
            "empresanro",
            "empresa_nro",
            "empresa",
            "nroempresa",
            "nrohabilitacioncnrt"
        ]
    )

    # --------------------------------------------------------
    # Filtrar por línea
    # --------------------------------------------------------

    mascara_linea = df[
        columna_linea
    ].apply(
        lambda valor: pertenece_a_linea(
            valor,
            linea
        )
    )

    resultado = df[
        mascara_linea
    ].copy()

    print(
        f"Línea {linea}: "
        f"{len(resultado)} vehículos "
        f"encontrados por columna '{columna_linea}'."
    )

    # --------------------------------------------------------
    # Si existe columna empresa, verificarla
    # --------------------------------------------------------

    if columna_empresa is not None:

        empresa_normalizada = (
            resultado[
                columna_empresa
            ]
            .apply(normalizar_empresa)
        )

        empresa_esperada = normalizar_empresa(
            empresa_esperada
        )

        # ----------------------------------------------------
        # Solo eliminar cuando la empresa está informada
        # y es diferente.
        #
        # Si está vacía, conservamos la fila porque el CSV
        # ya proviene de la empresa consultada.
        # ----------------------------------------------------

        mascara_empresa_valida = (
            (empresa_normalizada == "")
            |
            (
                empresa_normalizada
                == empresa_esperada
            )
        )

        eliminados = (
            len(resultado)
            - int(
                mascara_empresa_valida.sum()
            )
        )

        if eliminados > 0:

            print(
                f"Línea {linea}: "
                f"se eliminaron {eliminados} "
                "filas de otra empresa."
            )

        resultado = resultado[
            mascara_empresa_valida
        ].copy()

    return resultado


# ============================================================
# PROCESAR TODAS LAS LÍNEAS
# ============================================================

def procesar():

    CARPETA_CNRT.mkdir(
        parents=True,
        exist_ok=True
    )

    CARPETA_PARQUES.mkdir(
        parents=True,
        exist_ok=True
    )

    archivos = sorted(
        CARPETA_CNRT.glob(
            "empresa_*.csv"
        )
    )

    if not archivos:

        raise RuntimeError(
            "No se encontraron archivos "
            "empresa_*.csv en la carpeta cnrt."
        )

    print()
    print("=" * 70)
    print(
        "ACTUALIZADOR DE PARQUES CNRT"
    )
    print("=" * 70)

    print(
        f"Archivos CNRT encontrados: "
        f"{len(archivos)}"
    )

    print()

    # --------------------------------------------------------
    # Cargar todos los CSV
    # --------------------------------------------------------

    empresas_data = {}

    for archivo in archivos:

        coincidencia = re.search(
            r"empresa_(\d+)\.csv$",
            archivo.name,
            re.IGNORECASE
        )

        if not coincidencia:

            continue

        empresa = coincidencia.group(1)

        try:

            df = leer_csv_cnrt(
                archivo
            )

            empresas_data[
                empresa
            ] = df

        except Exception as error:

            print(
                f"ERROR leyendo {archivo}: "
                f"{error}"
            )

    # --------------------------------------------------------
    # Procesar cada línea configurada
    # --------------------------------------------------------

    total_lineas = 0

    for linea, empresa in sorted(
        LINEAS_EMPRESAS.items(),
        key=lambda item: int(item[0])
    ):

        linea = str(linea)
        empresa = str(empresa)

        total_lineas += 1

        print()
        print("=" * 70)

        print(
            f"PROCESANDO LÍNEA {linea}"
        )

        print(
            f"Empresa CNRT: {empresa}"
        )

        print("=" * 70)

        # ----------------------------------------------------
        # Buscar CSV de la empresa
        # ----------------------------------------------------

        df = empresas_data.get(
            empresa
        )

        if df is None:

            print(
                f"ADVERTENCIA: "
                f"no existe empresa_{empresa}.csv"
            )

            continue

        # ----------------------------------------------------
        # Filtrar
        # ----------------------------------------------------

        resultado = filtrar_por_linea(
            df,
            linea,
            empresa,
            f"empresa_{empresa}.csv"
        )

        # ----------------------------------------------------
        # Archivo de salida
        # ----------------------------------------------------

        archivo_salida = (
            CARPETA_PARQUES
            / f"linea{linea}.csv"
        )

        # ----------------------------------------------------
        # CASO ESPECIAL:
        # si no encontramos vehículos, NO sobrescribimos
        # automáticamente un archivo anterior válido.
        # ----------------------------------------------------

        if resultado.empty:

            print(
                f"ADVERTENCIA: "
                f"Línea {linea} quedó sin vehículos."
            )

            if archivo_salida.exists():

                print(
                    f"Se conserva el archivo existente: "
                    f"{archivo_salida}"
                )

            else:

                print(
                    f"No existe archivo anterior para "
                    f"Línea {linea}."
                )

            continue

        # ----------------------------------------------------
        # Guardar
        # ----------------------------------------------------

        resultado.to_csv(
            archivo_salida,
            index=False,
            encoding="utf-8-sig"
        )

        print(
            f"GUARDADO -> {archivo_salida}"
        )

        print(
            f"Vehículos Línea {linea}: "
            f"{len(resultado)}"
        )

        # ----------------------------------------------------
        # Diagnóstico especial Línea 195
        # ----------------------------------------------------

        if linea == "195":

            print()
            print(
                "DIAGNÓSTICO LÍNEA 195"
            )

            print(
                "-" * 50
            )

            print(
                f"Columna utilizada: "
                f"{buscar_columna(df, ['linea', 'lineanro', 'nrolinea', 'linea_nro'])}"
            )

            print(
                f"Vehículos encontrados: "
                f"{len(resultado)}"
            )

            if not resultado.empty:

                columna_linea = buscar_columna(
                    resultado,
                    [
                        "linea",
                        "lineanro",
                        "nrolinea",
                        "linea_nro"
                    ]
                )

                valores = (
                    resultado[
                        columna_linea
                    ]
                    .dropna()
                    .astype(str)
                    .drop_duplicates()
                    .head(20)
                    .tolist()
                )

                print(
                    "Ejemplos de valores CNRT:"
                )

                for valor in valores:

                    print(
                        f"  - {valor}"
                    )

    print()
    print("=" * 70)
    print(
        "ACTUALIZACIÓN COMPLETADA"
    )
    print("=" * 70)

    print(
        f"Líneas procesadas: "
        f"{total_lineas}"
    )

    print("=" * 70)


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

if __name__ == "__main__":

    procesar()
