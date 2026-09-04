# ============================================================
# LECTOR DE CONTROLES DESDE GOOGLE DRIVE
# ============================================================

import json
import os
import re
from pathlib import Path

import pandas as pd

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from configuracion_lineas import LINEAS_EMPRESAS


# ============================================================
# CONFIGURACIÓN
# ============================================================

DRIVE_FOLDER_ID = (
    "1lS7Ybqr4Knej93BCdun4pDLVZX3ldv59"
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]

CARPETA_CONTROLADOS = Path("controlados")
CARPETA_TEMP = Path("tmp_drive")

CARPETA_CONTROLADOS.mkdir(
    parents=True,
    exist_ok=True
)

CARPETA_TEMP.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# NORMALIZAR TEXTO
# ============================================================

def normalizar_texto(valor):

    if valor is None:
        return ""

    try:

        if pd.isna(valor):
            return ""

    except Exception:
        pass

    return str(valor).strip()


# ============================================================
# NORMALIZAR NOMBRE DE COLUMNA
# ============================================================

def normalizar_columna(nombre):

    texto = normalizar_texto(nombre).lower()

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
            nuevo
        )

    texto = re.sub(
        r"[^a-z0-9]",
        "",
        texto
    )

    return texto


# ============================================================
# EXTRAER LÍNEAS DE UN TEXTO
# ============================================================

def extraer_lineas_configuradas(valor):

    texto = normalizar_texto(valor).upper()

    if not texto:
        return []

    resultados = []

    # --------------------------------------------------------
    # CASO:
    #
    # LINEA 45
    # LINEA 51/74/79
    # LINEA 45-70-119
    # --------------------------------------------------------

    coincidencias = re.findall(
        r"\bLINEA(?:S)?\s*[:#-]?\s*([0-9][0-9\-/,\s]*)",
        texto
    )

    for coincidencia in coincidencias:

        numeros = re.findall(
            r"\d+",
            coincidencia
        )

        for numero in numeros:

            numero = int(numero)

            if numero in LINEAS_EMPRESAS:

                resultados.append(
                    numero
                )

    return list(
        dict.fromkeys(resultados)
    )


# ============================================================
# LÍNEAS EN NOMBRE DE ARCHIVO
# ============================================================

def lineas_del_nombre(nombre):

    texto = normalizar_texto(nombre).upper()

    resultados = extraer_lineas_configuradas(
        texto
    )

    # --------------------------------------------------------
    # Si el nombre no tiene "LINEA", intentar buscar
    # directamente números conocidos.
    # --------------------------------------------------------

    if not resultados:

        numeros = re.findall(
            r"\d+",
            texto
        )

        for numero in numeros:

            numero = int(numero)

            if numero in LINEAS_EMPRESAS:

                resultados.append(
                    numero
                )

    return list(
        dict.fromkeys(resultados)
    )


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

    try:

        datos = json.loads(
            contenido
        )

    except Exception as e:

        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON "
            "no contiene un JSON válido."
        ) from e

    return (
        service_account
        .Credentials
        .from_service_account_info(
            datos,
            scopes=SCOPES
        )
    )


# ============================================================
# CONECTAR DRIVE
# ============================================================

def obtener_drive():

    credenciales = obtener_credenciales()

    return build(
        "drive",
        "v3",
        credentials=credenciales,
    )


# ============================================================
# LISTAR TODOS LOS ARCHIVOS
# ============================================================

def listar_archivos(drive):

    archivos = []

    page_token = None

    while True:

        respuesta = (
            drive.files()
            .list(
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
                orderBy="name",
            )
            .execute()
        )

        encontrados = respuesta.get(
            "files",
            []
        )

        archivos.extend(
            encontrados
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
    mime = archivo.get(
        "mimeType",
        ""
    )

    # --------------------------------------------------------
    # GOOGLE SHEETS
    # --------------------------------------------------------

    if (
        mime
        == "application/vnd.google-apps.spreadsheet"
    ):

        nombre_seguro = re.sub(
            r'[\\/:*?"<>|]',
            "_",
            nombre
        )

        destino = (
            CARPETA_TEMP
            / f"{nombre_seguro}.xlsx"
        )

        request = (
            drive.files()
            .export_media(
                fileId=archivo_id,
                mimeType=(
                    "application/"
                    "vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            )
        )

    # --------------------------------------------------------
    # EXCEL
    # --------------------------------------------------------

    else:

        nombre_seguro = re.sub(
            r'[\\/:*?"<>|]',
            "_",
            nombre
        )

        destino = (
            CARPETA_TEMP
            / nombre_seguro
        )

        request = (
            drive.files()
            .get_media(
                fileId=archivo_id
            )
        )

    print(
        f"Descargando: {nombre}"
    )

    with open(
        destino,
        "wb"
    ) as archivo_salida:

        downloader = MediaIoBaseDownload(
            archivo_salida,
            request
        )

        terminado = False

        while not terminado:

            estado, terminado = (
                downloader.next_chunk()
            )

            if estado:

                print(
                    f"  Progreso: "
                    f"{int(estado.progress() * 100)}%"
                )

    return destino


# ============================================================
# LEER EXCEL
# ============================================================

def leer_excel(path):

    print(
        f"Leyendo archivo: {path.name}"
    )

    try:

        return pd.read_excel(
            path,
            sheet_name=None,
            header=None,
            dtype=str,
        )

    except Exception as e:

        print(
            f"ERROR leyendo "
            f"{path.name}: {e}"
        )

        return {}


# ============================================================
# BUSCAR POSICIONES DE ENCABEZADOS
# ============================================================

def posiciones_encabezados(valores):

    posiciones = {
        "fecha": None,
        "dominio": None,
        "interno": None,
    }

    for i, valor in enumerate(valores):

        nombre = normalizar_columna(
            valor
        )

        if nombre == "fecha":

            posiciones["fecha"] = i

        elif nombre == "dominio":

            posiciones["dominio"] = i

        elif nombre == "interno":

            posiciones["interno"] = i

    return posiciones


# ============================================================
# BUSCAR LÍNEA MÁS CERCANA
# ============================================================

def buscar_linea_para_bloque(
    df,
    fila_encabezado,
    columna_inicio,
    lineas_archivo
):

    # --------------------------------------------------------
    # Buscar hacia arriba hasta 15 filas.
    # --------------------------------------------------------

    fila_minima = max(
        0,
        fila_encabezado - 15
    )

    candidatos = []

    for fila_num in range(
        fila_minima,
        fila_encabezado
    ):

        fila = df.iloc[
            fila_num
        ].tolist()

        for columna_num, valor in enumerate(
            fila
        ):

            lineas = extraer_lineas_configuradas(
                valor
            )

            if not lineas:
                continue

            distancia = abs(
                columna_num
                - columna_inicio
            )

            candidatos.append(
                (
                    distancia,
                    fila_encabezado
                    - fila_num,
                    lineas
                )
            )

    # --------------------------------------------------------
    # Elegir encabezado más cercano
    # espacialmente al bloque.
    # --------------------------------------------------------

    if candidatos:

        candidatos.sort(
            key=lambda x: (
                x[0],
                x[1]
            )
        )

        lineas = candidatos[0][2]

        if lineas:

            return lineas[0]

    # --------------------------------------------------------
    # Si no encontramos encabezado dentro de la hoja,
    # usar nombre del archivo únicamente si tiene una
    # sola línea.
    # --------------------------------------------------------

    if len(lineas_archivo) == 1:

        return lineas_archivo[0]

    return None


# ============================================================
# EXTRAER BLOQUES DE UNA HOJA
# ============================================================

def extraer_bloques(
    df,
    lineas_archivo,
    nombre_hoja
):

    controles = []

    if df is None or df.empty:

        return controles

    df = df.fillna("")

    # --------------------------------------------------------
    # BUSCAR TODAS LAS FILAS QUE CONTIENEN "LINEA"
    # --------------------------------------------------------

    encabezados_linea = []

    for fila_num in range(
        len(df)
    ):

        fila = df.iloc[
            fila_num
        ].tolist()

        for columna_num, valor in enumerate(
            fila
        ):

            lineas = extraer_lineas_configuradas(
                valor
            )

            if lineas:

                encabezados_linea.append(
                    (
                        fila_num,
                        columna_num,
                        lineas
                    )
                )

    print(
        f"  Hoja '{nombre_hoja}': "
        f"{len(encabezados_linea)} "
        f"encabezados de línea detectados."
    )

    # --------------------------------------------------------
    # BUSCAR TODAS LAS FILAS DE COLUMNAS
    # --------------------------------------------------------

    encabezados_datos = []

    for fila_num in range(
        len(df)
    ):

        valores = [
            normalizar_texto(v)
            for v in df.iloc[
                fila_num
            ].tolist()
        ]

        posiciones = posiciones_encabezados(
            valores
        )

        if (
            posiciones["fecha"] is not None
            and posiciones["dominio"] is not None
            and posiciones["interno"] is not None
        ):

            encabezados_datos.append(
                (
                    fila_num,
                    posiciones
                )
            )

    print(
        f"  Hoja '{nombre_hoja}': "
        f"{len(encabezados_datos)} "
        f"bloques de datos detectados."
    )

    # --------------------------------------------------------
    # PROCESAR CADA BLOQUE
    # --------------------------------------------------------

    for indice_bloque, (
        fila_encabezado,
        posiciones
    ) in enumerate(encabezados_datos):

        columna_fecha = posiciones[
            "fecha"
        ]

        columna_dominio = posiciones[
            "dominio"
        ]

        columna_interno = posiciones[
            "interno"
        ]

        columna_inicio = min(
            columna_fecha,
            columna_dominio,
            columna_interno
        )

        # ----------------------------------------------------
        # DETERMINAR LÍNEA
        # ----------------------------------------------------

        linea = buscar_linea_para_bloque(
            df,
            fila_encabezado,
            columna_inicio,
            lineas_archivo
        )

        if linea is None:

            print(
                f"  Bloque {indice_bloque + 1}: "
                "no se pudo determinar la línea. "
                "Se ignora."
            )

            continue

        print(
            f"  Bloque {indice_bloque + 1}: "
            f"Línea {linea}"
        )

        # ----------------------------------------------------
        # DÓNDE TERMINA EL BLOQUE
        # ----------------------------------------------------

        siguiente_encabezado = len(df)

        if (
            indice_bloque + 1
            < len(encabezados_datos)
        ):

            siguiente_encabezado = (
                encabezados_datos[
                    indice_bloque + 1
                ][0]
            )

        # ----------------------------------------------------
        # LEER FILAS
        # ----------------------------------------------------

        for fila_num in range(
            fila_encabezado + 1,
            siguiente_encabezado
        ):

            fila = df.iloc[
                fila_num
            ].tolist()

            max_pos = max(
                columna_fecha,
                columna_dominio,
                columna_interno
            )

            if len(fila) <= max_pos:
                continue

            # ------------------------------------------------
            # SI APARECE OTRO "LINEA", TERMINAR BLOQUE
            # ------------------------------------------------

            contiene_nueva_linea = False

            for valor in fila:

                if extraer_lineas_configuradas(
                    valor
                ):

                    contiene_nueva_linea = True
                    break

            if contiene_nueva_linea:

                break

            # ------------------------------------------------
            # EXTRAER DATOS
            # ------------------------------------------------

            fecha = normalizar_texto(
                fila[columna_fecha]
            )

            dominio = normalizar_texto(
                fila[columna_dominio]
            ).upper()

            interno = normalizar_texto(
                fila[columna_interno]
            )

            # ------------------------------------------------
            # VALIDACIONES
            # ------------------------------------------------

            if not fecha:
                continue

            if not dominio:
                continue

            if not interno:
                continue

            if (
                normalizar_columna(dominio)
                == "dominio"
            ):
                continue

            # ------------------------------------------------
            # GUARDAR
            # ------------------------------------------------

            controles.append(
                {
                    "fecha": fecha,
                    "dominio": dominio,
                    "interno": interno,
                    "linea": str(linea),
                }
            )

    return controles


# ============================================================
# PROCESAR ARCHIVO COMPLETO
# ============================================================

def procesar_archivo(path):

    lineas_archivo = lineas_del_nombre(
        path.name
    )

    print(
        f"Líneas detectadas por nombre: "
        f"{lineas_archivo}"
    )

    hojas = leer_excel(
        path
    )

    todos = []

    for nombre_hoja, df in hojas.items():

        print()
        print(
            f"Procesando hoja: "
            f"{nombre_hoja}"
        )

        controles = extraer_bloques(
            df,
            lineas_archivo,
            nombre_hoja
        )

        todos.extend(
            controles
        )

    return todos


# ============================================================
# GUARDAR CONTROLES
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
    # ASEGURAR COLUMNAS
    # --------------------------------------------------------

    columnas = [
        "fecha",
        "dominio",
        "interno",
        "linea",
    ]

    for columna in columnas:

        if columna not in df_nuevo.columns:

            df_nuevo[columna] = ""

    df_nuevo = df_nuevo[
        columnas
    ]

    # --------------------------------------------------------
    # TODAS LAS LÍNEAS DETECTADAS
    # --------------------------------------------------------

    lineas = sorted(
        set(
            df_nuevo["linea"]
            .astype(str)
            .tolist()
        )
    )

    for linea_texto in lineas:

        try:

            linea = int(
                linea_texto
            )

        except ValueError:

            continue

        if linea not in LINEAS_EMPRESAS:

            print(
                f"Ignorando línea {linea}: "
                "no está configurada."
            )

            continue

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
        # LEER EXISTENTES
        # ----------------------------------------------------

        if archivo.exists():

            try:

                df_existente = pd.read_csv(
                    archivo,
                    dtype=str,
                    keep_default_na=False,
                    encoding="utf-8-sig"
                )

            except Exception as e:

                print(
                    f"Advertencia leyendo "
                    f"{archivo}: {e}"
                )

                df_existente = pd.DataFrame()

        else:

            df_existente = pd.DataFrame()

        # ----------------------------------------------------
        # UNIR
        # ----------------------------------------------------

        df_final = pd.concat(
            [
                df_existente,
                df_linea
            ],
            ignore_index=True,
            sort=False
        )

        # ----------------------------------------------------
        # ASEGURAR COLUMNAS
        # ----------------------------------------------------

        for columna in columnas:

            if columna not in df_final.columns:

                df_final[columna] = ""

        df_final = df_final[
            columnas
        ]

        # ----------------------------------------------------
        # NORMALIZAR
        # ----------------------------------------------------

        for columna in columnas:

            df_final[columna] = (
                df_final[columna]
                .astype(str)
                .str.strip()
            )

        df_final["dominio"] = (
            df_final["dominio"]
            .str.upper()
        )

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
            keep="last"
        )

        # ----------------------------------------------------
        # ORDENAR
        # ----------------------------------------------------

        df_final = df_final.sort_values(
            by=[
                "fecha",
                "dominio"
            ],
            kind="stable"
        )

        # ----------------------------------------------------
        # GUARDAR
        # ----------------------------------------------------

        df_final.to_csv(
            archivo,
            index=False,
            encoding="utf-8-sig"
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

    print()
    print("=" * 60)
    print(
        "ACTUALIZADOR DE CONTROLADOS DESDE GOOGLE DRIVE"
    )
    print("=" * 60)
    print()

    drive = obtener_drive()

    # --------------------------------------------------------
    # TODOS LOS ARCHIVOS DE LA CARPETA
    # --------------------------------------------------------

    archivos = listar_archivos(
        drive
    )

    print(
        f"Archivos encontrados en Drive: "
        f"{len(archivos)}"
    )

    todos_los_controles = []

    # --------------------------------------------------------
    # PROCESAR TODO
    # --------------------------------------------------------

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
        # TIPOS VÁLIDOS
        # ----------------------------------------------------

        extensiones_validas = (
            ".xlsx",
            ".xls",
            ".xlsm",
        )

        es_google_sheet = (
            mime
            == "application/vnd.google-apps.spreadsheet"
        )

        es_excel = (
            nombre.lower().endswith(
                extensiones_validas
            )
        )

        if not es_google_sheet and not es_excel:

            print(
                f"Ignorando archivo no compatible: "
                f"{nombre}"
            )

            continue

        # ----------------------------------------------------
        # PROCESAR
        # ----------------------------------------------------

        print()
        print("-" * 60)
        print(
            f"PROCESANDO: {nombre}"
        )
        print("-" * 60)

        try:

            path = descargar_archivo(
                drive,
                archivo
            )

            controles = procesar_archivo(
                path
            )

            print(
                f"Controles encontrados en archivo: "
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

    # --------------------------------------------------------
    # TOTAL
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print(
        f"TOTAL DE CONTROLES ENCONTRADOS: "
        f"{len(todos_los_controles)}"
    )
    print("=" * 60)

    # --------------------------------------------------------
    # GUARDAR
    # --------------------------------------------------------

    guardar_controles(
        todos_los_controles
    )

    print()
    print("=" * 60)
    print(
        "ACTUALIZACIÓN DE CONTROLADOS TERMINADA"
    )
    print("=" * 60)
    print()


if __name__ == "__main__":

    main()
