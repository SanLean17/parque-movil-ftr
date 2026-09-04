# ============================================================
# LECTOR DE CONTROLES DESDE GOOGLE DRIVE
# ============================================================

import io
import os
import re
import csv
from pathlib import Path
from datetime import datetime

import pandas as pd

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from configuracion_lineas import LINEAS_EMPRESAS


# ============================================================
# CONFIGURACIÓN
# ============================================================

DRIVE_FOLDER_ID = "1lS7Ybqr4Knej93BCdun4pDLVZX3ldv59"

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]

CARPETA_CONTROLADOS = Path("controlados")
CARPETA_CONTROLADOS.mkdir(exist_ok=True)

CARPETA_TEMP = Path("tmp_drive")
CARPETA_TEMP.mkdir(exist_ok=True)


# ============================================================
# AUTENTICACIÓN
# ============================================================

def obtener_credenciales():

    contenido = os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    )

    if not contenido:
        raise RuntimeError(
            "No existe la variable "
            "GOOGLE_SERVICE_ACCOUNT_JSON."
        )

    credenciales = (
        service_account
        .Credentials
        .from_service_account_info(
            __import__("json").loads(contenido),
            scopes=SCOPES,
        )
    )

    return credenciales


def obtener_drive():

    credenciales = obtener_credenciales()

    return build(
        "drive",
        "v3",
        credentials=credenciales,
    )


# ============================================================
# LISTAR ARCHIVOS
# ============================================================

def listar_archivos(drive):

    archivos = []

    page_token = None

    while True:

        respuesta = drive.files().list(
            q=(
                f"'{DRIVE_FOLDER_ID}' in parents "
                "and trashed = false"
            ),
            fields=(
                "nextPageToken,"
                "files("
                "id,"
                "name,"
                "mimeType,"
                "modifiedTime"
                ")"
            ),
            pageSize=1000,
            pageToken=page_token,
        ).execute()

        archivos.extend(
            respuesta.get("files", [])
        )

        page_token = respuesta.get(
            "nextPageToken"
        )

        if not page_token:
            break

    return archivos


# ============================================================
# DESCARGAR ARCHIVO
# ============================================================

def descargar_archivo(drive, archivo):

    archivo_id = archivo["id"]
    nombre = archivo["name"]

    destino = CARPETA_TEMP / nombre

    request = drive.files().get_media(
        fileId=archivo_id
    )

    with open(destino, "wb") as f:

        downloader = MediaIoBaseDownload(
            f,
            request,
        )

        terminado = False

        while not terminado:

            estado, terminado = (
                downloader.next_chunk()
            )

            if estado:
                print(
                    f"  Descargando {nombre}: "
                    f"{int(estado.progress() * 100)}%"
                )

    return destino


# ============================================================
# DETECTAR LÍNEAS EN EL NOMBRE DEL ARCHIVO
# ============================================================

def lineas_del_nombre(nombre):

    texto = str(nombre).upper()

    # Ejemplos:
    #
    # LINEA 45-70-119-154-179
    # LINEA 51/74/79/164/177
    # LINEA 195
    #
    match = re.search(
        r"LINEA\s+(.+)",
        texto,
    )

    if not match:
        return []

    parte = match.group(1)

    numeros = re.findall(
        r"\d+",
        parte,
    )

    resultado = []

    for numero in numeros:

        numero = int(numero)

        if numero in LINEAS_EMPRESAS:
            resultado.append(numero)

    return list(dict.fromkeys(resultado))


# ============================================================
# DETECTAR UNA LÍNEA EN UNA CELDA
# ============================================================

def detectar_lineas_texto(valor):

    if valor is None:
        return []

    texto = str(valor).strip().upper()

    if not texto:
        return []

    # Buscamos específicamente "LINEA" seguido de números.
    #
    # Ejemplo:
    # LINEA 45
    # LINEA 70
    # LINEA 45-70-119
    # LINEA 51/74/79

    resultados = []

    coincidencias = re.findall(
        r"LINEA\s+([0-9][0-9\-/]*)",
        texto,
    )

    for coincidencia in coincidencias:

        numeros = re.findall(
            r"\d+",
            coincidencia,
        )

        for numero in numeros:

            numero = int(numero)

            if numero in LINEAS_EMPRESAS:
                resultados.append(numero)

    return list(dict.fromkeys(resultados))


# ============================================================
# NORMALIZAR TEXTO
# ============================================================

def normalizar_texto(valor):

    if pd.isna(valor):
        return ""

    return str(valor).strip()


# ============================================================
# IDENTIFICAR COLUMNAS
# ============================================================

def normalizar_columna(nombre):

    texto = str(nombre).strip().lower()

    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }

    for viejo, nuevo in reemplazos.items():
        texto = texto.replace(
            viejo,
            nuevo,
        )

    texto = re.sub(
        r"[^a-z0-9]",
        "",
        texto,
    )

    return texto


def encontrar_columna(columnas, posibles):

    mapa = {
        normalizar_columna(col): col
        for col in columnas
    }

    for posible in posibles:

        clave = normalizar_columna(
            posible
        )

        if clave in mapa:
            return mapa[clave]

    return None


# ============================================================
# LEER EXCEL
# ============================================================

def leer_excel(path):

    print(
        f"Leyendo hoja: {path.name}"
    )

    try:

        hojas = pd.read_excel(
            path,
            sheet_name=None,
            header=None,
        )

        return hojas

    except Exception as e:

        print(
            f"ERROR leyendo {path.name}: {e}"
        )

        return {}


# ============================================================
# EXTRAER BLOQUES
# ============================================================

def extraer_bloques(df, lineas_archivo):

    controles = []

    linea_actual = None

    columnas_fecha = None
    columnas_dominio = None
    columnas_interno = None

    filas = df.fillna("")

    for indice, fila in filas.iterrows():

        valores = [
            normalizar_texto(v)
            for v in fila.tolist()
        ]

        # ----------------------------------------------------
        # BUSCAR "LINEA XX"
        # ----------------------------------------------------

        nuevas_lineas = []

        for valor in valores:

            detectadas = detectar_lineas_texto(
                valor
            )

            nuevas_lineas.extend(
                detectadas
            )

        nuevas_lineas = list(
            dict.fromkeys(nuevas_lineas)
        )

        if nuevas_lineas:

            # Si aparece un encabezado "LINEA XX",
            # comienza un nuevo bloque.
            #
            # En el caso de una línea individual:
            # LINEA 195
            #
            # En el caso de un archivo combinado:
            # LINEA 45
            # LINEA 70
            # etc.

            linea_actual = nuevas_lineas[0]

            columnas_fecha = None
            columnas_dominio = None
            columnas_interno = None

            continue

        # ----------------------------------------------------
        # BUSCAR ENCABEZADOS
        # ----------------------------------------------------

        nombres_normalizados = [
            normalizar_columna(v)
            for v in valores
        ]

        pos_fecha = None
        pos_dominio = None
        pos_interno = None

        for i, nombre in enumerate(
            nombres_normalizados
        ):

            if nombre == "fecha":
                pos_fecha = i

            elif nombre == "dominio":
                pos_dominio = i

            elif nombre == "interno":
                pos_interno = i

        if (
            pos_fecha is not None
            and pos_dominio is not None
            and pos_interno is not None
        ):

            columnas_fecha = pos_fecha
            columnas_dominio = pos_dominio
            columnas_interno = pos_interno

            continue

        # ----------------------------------------------------
        # SI NO HAY LÍNEA ACTUAL, INTENTAMOS CON EL NOMBRE
        # DEL ARCHIVO
        # ----------------------------------------------------

        if linea_actual is None:

            if len(lineas_archivo) == 1:

                linea_actual = (
                    lineas_archivo[0]
                )

            else:
                continue

        # ----------------------------------------------------
        # SI NO TENEMOS COLUMNAS, CONTINUAR
        # ----------------------------------------------------

        if (
            columnas_fecha is None
            or columnas_dominio is None
            or columnas_interno is None
        ):
            continue

        # ----------------------------------------------------
        # ASEGURAR CANTIDAD DE COLUMNAS
        # ----------------------------------------------------

        max_pos = max(
            columnas_fecha,
            columnas_dominio,
            columnas_interno,
        )

        if len(valores) <= max_pos:
            continue

        fecha = normalizar_texto(
            valores[columnas_fecha]
        )

        dominio = normalizar_texto(
            valores[columnas_dominio]
        ).upper()

        interno = normalizar_texto(
            valores[columnas_interno]
        )

        # ----------------------------------------------------
        # VALIDAR DOMINIO
        # ----------------------------------------------------

        if not dominio:
            continue

        # No aceptar la palabra "dominio" como dato.
        if dominio.lower() == "dominio":
            continue

        # ----------------------------------------------------
        # VALIDAR FECHA
        # ----------------------------------------------------

        if not fecha:
            continue

        # ----------------------------------------------------
        # VALIDAR INTERNO
        # ----------------------------------------------------

        if not interno:
            continue

        # ----------------------------------------------------
        # GUARDAR CONTROL
        # ----------------------------------------------------

        controles.append(
            {
                "fecha": fecha,
                "dominio": dominio,
                "interno": interno,
                "linea": str(linea_actual),
            }
        )

    return controles


# ============================================================
# PROCESAR ARCHIVO
# ============================================================

def procesar_archivo(path):

    lineas_archivo = lineas_del_nombre(
        path.name
    )

    if not lineas_archivo:

        print(
            f"  -> No se detectaron líneas "
            f"en el nombre: {path.name}"
        )

        return []

    print(
        f"  Líneas detectadas en nombre: "
        f"{lineas_archivo}"
    )

    hojas = leer_excel(path)

    todos = []

    for nombre_hoja, df in hojas.items():

        print(
            f"  Hoja: {nombre_hoja}"
        )

        controles = extraer_bloques(
            df,
            lineas_archivo,
        )

        todos.extend(controles)

    return todos


# ============================================================
# GUARDAR CONTROLADOS
# ============================================================

def guardar_controles(controles):

    if not controles:

        print(
            "No se encontraron controles."
        )

        return

    df_nuevo = pd.DataFrame(
        controles
    )

    # --------------------------------------------------------
    # UNA LÍNEA POR ARCHIVO
    # --------------------------------------------------------

    for linea in sorted(
        df_nuevo["linea"]
        .astype(int)
        .unique()
    ):

        df_linea = df_nuevo[
            df_nuevo["linea"].astype(int)
            == linea
        ].copy()

        if df_linea.empty:
            continue

        archivo = (
            CARPETA_CONTROLADOS
            / f"linea{linea}.csv"
        )

        # ----------------------------------------------------
        # LEER DATOS EXISTENTES
        # ----------------------------------------------------

        if archivo.exists():

            try:

                df_existente = pd.read_csv(
                    archivo,
                    dtype=str,
                    keep_default_na=False,
                    encoding="utf-8-sig",
                )

            except Exception:

                df_existente = pd.DataFrame()

        else:

            df_existente = pd.DataFrame()

        # ----------------------------------------------------
        # UNIR
        # ----------------------------------------------------

        df_final = pd.concat(
            [
                df_existente,
                df_linea,
            ],
            ignore_index=True,
        )

        # ----------------------------------------------------
        # NORMALIZAR
        # ----------------------------------------------------

        columnas = [
            "fecha",
            "dominio",
            "interno",
            "linea",
        ]

        for columna in columnas:

            if columna not in df_final.columns:
                df_final[columna] = ""

        df_final = df_final[
            columnas
        ]

        # ----------------------------------------------------
        # ELIMINAR DUPLICADOS
        # ----------------------------------------------------

        df_final = df_final.drop_duplicates(
            subset=[
                "fecha",
                "dominio",
                "interno",
                "linea",
            ],
            keep="last",
        )

        # ----------------------------------------------------
        # ORDENAR
        # ----------------------------------------------------

        df_final = df_final.sort_values(
            by=[
                "fecha",
                "dominio",
            ],
            kind="stable",
        )

        # ----------------------------------------------------
        # GUARDAR
        # ----------------------------------------------------

        df_final.to_csv(
            archivo,
            index=False,
            encoding="utf-8-sig",
        )

        print(
            f"Línea {linea}: "
            f"{len(df_final)} controles -> "
            f"{archivo}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("=" * 60)
    print("ACTUALIZADOR DE CONTROLADOS DESDE GOOGLE DRIVE")
    print("=" * 60)
    print("")

    drive = obtener_drive()

    archivos = listar_archivos(
        drive
    )

    print(
        f"Archivos encontrados en Drive: "
        f"{len(archivos)}"
    )

    todos_los_controles = []

    for archivo in archivos:

        nombre = archivo.get(
            "name",
            ""
        )

        mime = archivo.get(
            "mimeType",
            ""
        )

        # ----------------------------------------------------
        # SOLO EXCEL
        # ----------------------------------------------------

        extensiones_validas = (
            ".xlsx",
            ".xls",
            ".xlsm",
        )

        if not nombre.lower().endswith(
            extensiones_validas
        ):

            print(
                f"Ignorando: {nombre}"
            )

            continue

        print("")
        print(
            f"Procesando: {nombre}"
        )

        try:

            path = descargar_archivo(
                drive,
                archivo,
            )

            controles = procesar_archivo(
                path
            )

            print(
                f"  Controles encontrados: "
                f"{len(controles)}"
            )

            todos_los_controles.extend(
                controles
            )

        except Exception as e:

            print(
                f"ERROR procesando "
                f"{nombre}: {e}"
            )

    print("")
    print(
        f"TOTAL DE CONTROLES ENCONTRADOS: "
        f"{len(todos_los_controles)}"
    )

    guardar_controles(
        todos_los_controles
    )

    print("")
    print("=" * 60)
    print("ACTUALIZACIÓN DE CONTROLADOS TERMINADA")
    print("=" * 60)
    print("")


if __name__ == "__main__":
    main()
