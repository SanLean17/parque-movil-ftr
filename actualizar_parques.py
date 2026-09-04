import pandas as pd
from pathlib import Path
import re
import shutil


CARPETA_CNRT = Path("cnrt")
CARPETA_PARQUES = Path("parques")
CARPETA_CONTROLADOS = Path("controlados")

ARCHIVO_CNRT = CARPETA_CNRT / "empresa_2062.csv"


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Empresa GENERAL TOMAS GUIDO S.A.C.I.F.
EMPRESA_CNRT = "2062"

# Líneas que vamos a actualizar desde esta empresa.
LINEAS_A_ACTUALIZAR = {
    "9",
    "164",
}


# ============================================================
# CREAR CARPETAS
# ============================================================

CARPETA_CNRT.mkdir(exist_ok=True)
CARPETA_PARQUES.mkdir(exist_ok=True)
CARPETA_CONTROLADOS.mkdir(exist_ok=True)


# ============================================================
# LECTURA ROBUSTA DEL CSV
# ============================================================

def leer_csv_robusto(path):

    separadores = [";", ","]

    for separador in separadores:

        try:

            df = pd.read_csv(
                path,
                encoding="utf-8-sig",
                dtype=str,
                sep=separador
            )

            if len(df.columns) > 1:
                return df

        except Exception:
            pass

    raise RuntimeError(
        f"No se pudo leer correctamente el CSV: {path}"
    )


# ============================================================
# NORMALIZACIÓN DE COLUMNAS
# ============================================================

def normalizar_nombre_columna(nombre):

    return (
        str(nombre)
        .strip()
        .lower()
        .replace("_", "")
        .replace(" ", "")
    )


def obtener_columna(df, nombres):

    nombres_normalizados = {
        normalizar_nombre_columna(x)
        for x in nombres
    }

    for columna in df.columns:

        nombre = normalizar_nombre_columna(columna)

        if nombre in nombres_normalizados:
            return columna

    return None


# ============================================================
# OBTENER COLUMNA LINEA
# ============================================================

def obtener_columna_linea(df):

    return obtener_columna(
        df,
        [
            "linea",
            "lineanro",
            "nrolinea",
            "linea_nro"
        ]
    )


# ============================================================
# OBTENER COLUMNA DOMINIO
# ============================================================

def obtener_columna_dominio(df):

    return obtener_columna(
        df,
        [
            "dominio",
            "patente",
            "dominio_vehiculo"
        ]
    )


# ============================================================
# NORMALIZAR LÍNEA
# ============================================================

def normalizar_linea(valor):

    if pd.isna(valor):
        return ""

    valor = str(valor).strip()

    # Ejemplo:
    # "9" → "9"
    # "09" → "9"
    # "9.0" → "9"

    try:

        numero = float(valor)

        if numero.is_integer():
            return str(int(numero))

    except Exception:
        pass

    return valor


# ============================================================
# VALIDAR CSV CNRT
# ============================================================

def validar_csv_cnrt(df):

    if df is None or df.empty:

        raise RuntimeError(
            "El CSV descargado desde CNRT está vacío."
        )

    columna_linea = obtener_columna_linea(df)

    if columna_linea is None:

        raise RuntimeError(
            "El CSV de CNRT no contiene la columna 'linea'."
        )

    columna_dominio = obtener_columna_dominio(df)

    if columna_dominio is None:

        raise RuntimeError(
            "El CSV de CNRT no contiene la columna 'dominio'."
        )

    print(
        f"Columna línea encontrada: {columna_linea}"
    )

    print(
        f"Columna dominio encontrada: {columna_dominio}"
    )


# ============================================================
# FILTRAR UNA LÍNEA
# ============================================================

def filtrar_linea(df, numero_linea):

    columna_linea = obtener_columna_linea(df)

    if columna_linea is None:

        raise RuntimeError(
            "No existe columna línea."
        )

    valores = (
        df[columna_linea]
        .fillna("")
        .apply(normalizar_linea)
    )

    linea_buscada = normalizar_linea(
        numero_linea
    )

    resultado = df[
        valores == linea_buscada
    ].copy()

    return resultado


# ============================================================
# LIMPIAR FILAS
# ============================================================

def limpiar_dataframe(df):

    if df is None or df.empty:
        return df

    columna_dominio = obtener_columna_dominio(df)

    if columna_dominio is not None:

        df = df[
            df[columna_dominio]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.len() >= 6
        ].copy()

    return df


# ============================================================
# ACTUALIZAR PARQUE DE UNA LÍNEA
# ============================================================

def actualizar_parque_linea(df_nuevo, numero_linea):

    numero_linea = str(numero_linea)

    archivo_parque = (
        CARPETA_PARQUES /
        f"linea{numero_linea}.csv"
    )

    archivo_controlados = (
        CARPETA_CONTROLADOS /
        f"linea{numero_linea}.csv"
    )

    # --------------------------------------------------------
    # FILTRAR ÚNICAMENTE LA LÍNEA
    # --------------------------------------------------------

    nuevo = filtrar_linea(
        df_nuevo,
        numero_linea
    )

    nuevo = limpiar_dataframe(nuevo)

    if nuevo.empty:

        raise RuntimeError(
            f"CNRT devolvió 0 vehículos para línea "
            f"{numero_linea}. "
            f"No se reemplazará el archivo existente."
        )

    # --------------------------------------------------------
    # MOSTRAR INFORMACIÓN
    # --------------------------------------------------------

    print()
    print("----------------------------------------")
    print(f"LÍNEA {numero_linea}")
    print("----------------------------------------")
    print(
        f"Vehículos encontrados en CNRT: {len(nuevo)}"
    )

    # --------------------------------------------------------
    # GUARDAR PARQUE NUEVO
    # --------------------------------------------------------

    nuevo.to_csv(
        archivo_parque,
        index=False,
        encoding="utf-8-sig",
        sep=";"
    )

    print(
        f"Parque actualizado: {archivo_parque}"
    )

    # --------------------------------------------------------
    # CONSERVAR CONTROLADOS
    # --------------------------------------------------------

    if not archivo_controlados.exists():

        print(
            "No existe archivo de controlados. "
            "No se crea ninguno automáticamente."
        )

        return

    try:

        controlados = leer_csv_robusto(
            archivo_controlados
        )

    except Exception as e:

        print(
            f"No se pudo leer controlados de "
            f"línea {numero_linea}: {e}"
        )

        return

    if controlados.empty:

        print(
            "El archivo de controlados está vacío."
        )

        return

    columna_dominio_nuevo = obtener_columna_dominio(
        nuevo
    )

    columna_dominio_controlado = obtener_columna_dominio(
        controlados
    )

    if (
        columna_dominio_nuevo is None
        or columna_dominio_controlado is None
    ):

        print(
            "No se pudo identificar la columna dominio "
            "en controlados."
        )

        return

    # Dominios que actualmente siguen en CNRT
    dominios_actuales = set(
        nuevo[columna_dominio_nuevo]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Filtrar controlados para que solamente permanezcan
    # los vehículos que siguen perteneciendo a la línea.
    controlados_filtrados = controlados[
        controlados[
            columna_dominio_controlado
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .isin(dominios_actuales)
    ].copy()

    controlados_filtrados.to_csv(
        archivo_controlados,
        index=False,
        encoding="utf-8-sig",
        sep=";"
    )

    print(
        "Controlados conservados:",
        len(controlados_filtrados)
    )


# ============================================================
# PROCESAR TODO
# ============================================================

def procesar():

    print()
    print("========================================")
    print(" ACTUALIZACIÓN DE PARQUES FTR")
    print("========================================")

    # --------------------------------------------------------
    # COMPROBAR CSV CNRT
    # --------------------------------------------------------

    if not ARCHIVO_CNRT.exists():

        raise RuntimeError(
            f"No existe el archivo descargado desde CNRT: "
            f"{ARCHIVO_CNRT}"
        )

    print(
        f"Leyendo CSV CNRT: {ARCHIVO_CNRT}"
    )

    df = leer_csv_robusto(
        ARCHIVO_CNRT
    )

    validar_csv_cnrt(df)

    print(
        f"Total registros descargados de CNRT: {len(df)}"
    )

    # --------------------------------------------------------
    # COMPROBAR EMPRESA
    # --------------------------------------------------------

    columna_empresa = obtener_columna(
        df,
        [
            "empresaNro",
            "empresa",
            "nroEmpresa",
            "nroHabilitacionCNRT"
        ]
    )

    if columna_empresa is not None:

        valores_empresa = (
            df[columna_empresa]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        coincidencias = valores_empresa == EMPRESA_CNRT

        cantidad = int(coincidencias.sum())

        print(
            f"Registros de empresa {EMPRESA_CNRT}: "
            f"{cantidad}"
        )

        if cantidad == 0:

            raise RuntimeError(
                f"El CSV no contiene registros de "
                f"la empresa CNRT {EMPRESA_CNRT}."
            )

        df = df[coincidencias].copy()

    else:

        print(
            "ADVERTENCIA: no se encontró columna "
            "de empresa. Se utilizará el resultado "
            "tal como fue devuelto por la consulta CNRT."
        )

    # --------------------------------------------------------
    # MOSTRAR LÍNEAS ENCONTRADAS
    # --------------------------------------------------------

    columna_linea = obtener_columna_linea(df)

    lineas_encontradas = (
        df[columna_linea]
        .fillna("")
        .apply(normalizar_linea)
        .value_counts()
        .sort_index()
    )

    print()
    print("Líneas encontradas en la descarga:")

    for linea, cantidad in lineas_encontradas.items():

        if linea:
            print(
                f"  Línea {linea}: {cantidad}"
            )

    # --------------------------------------------------------
    # ACTUALIZAR LÍNEAS CONFIGURADAS
    # --------------------------------------------------------

    for numero_linea in sorted(
        LINEAS_A_ACTUALIZAR,
        key=lambda x: int(x)
    ):

        actualizar_parque_linea(
            df,
            numero_linea
        )

    print()
    print("========================================")
    print(" ACTUALIZACIÓN FINALIZADA")
    print("========================================")


if __name__ == "__main__":
    procesar()
