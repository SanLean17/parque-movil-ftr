# ============================================================
# LEER CONTROLADOS DESDE GOOGLE DRIVE
# PARQUE MÓVIL FTR
# ============================================================

from pathlib import Path
import io
import json
import re

import pandas as pd

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from openpyxl import load_workbook

from configuracion_lineas import LINEAS_EMPRESAS


# ============================================================
# CONFIGURACIÓN
# ============================================================

CARPETA_CONTROLADOS = Path("controlados")

ID_CARPETA_DRIVE = (
    "1lS7Ybqr4Knej93BCdun4pDLVZX3ldv59"
)

GOOGLE_SERVICE_ACCOUNT_JSON = (
    "GOOGLE_SERVICE_ACCOUNT_JSON"
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly"
]


# ============================================================
# NORMALIZAR TEXTO
# ============================================================

def limpiar_texto(valor):

    if valor is None:
        return ""

    if pd.isna(valor):
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(valor)
    ).strip()


# ============================================================
# NORMALIZAR DOMINIO
# ============================================================

def normalizar_dominio(valor):

    texto = limpiar_texto(valor)

    if not texto:
        return ""

    return texto.upper()


# ============================================================
# NORMALIZAR INTERNO
# ============================================================

def normalizar_interno(valor):

    texto = limpiar_texto(valor)

    if not texto:
        return ""

    return texto


# ============================================================
# EXTRAER NÚMEROS DE LÍNEA
# ============================================================

def extraer_numeros_linea(texto):

    """
    Detecta líneas dentro de textos como:

        LINEA 63
        Línea 113
        63
        63/113
        LINEA 63/113
        LINEA 51/74/79/164/177

    IMPORTANTE:
    Solo devuelve números que realmente estén configurados
    en LINEAS_EMPRESAS.
    """

    texto = limpiar_texto(texto)

    if not texto:
        return set()

    lineas_configuradas = {
        str(linea)
        for linea in LINEAS_EMPRESAS.keys()
    }

    encontrados = set()

    # --------------------------------------------------------
    # Buscar números completos
    # --------------------------------------------------------

    numeros = re.findall(
        r"(?<!\d)(\d+)(?!\d)",
        texto
    )

    for numero in numeros:

        if numero in lineas_configuradas:

            encontrados.add(numero)

    return encontrados


# ============================================================
# DETERMINAR SI UNA CELDA ES ENCABEZADO DE LÍNEA
# ============================================================

def detectar_lineas_en_celda(valor):

    texto = limpiar_texto(valor)

    if not texto:
        return set()

    # --------------------------------------------------------
    # Tiene que parecer un encabezado de línea.
    #
    # Permitimos:
    #
    # LINEA 63
    # LÍNEA 63
    # LINEA 63/113
    # 63
    #
    # Pero evitamos tomar cualquier número perdido dentro
    # de una fecha, dominio, etc.
    # --------------------------------------------------------

    texto_mayuscula = texto.upper()

    if (
        "LINEA" in texto_mayuscula
        or "LÍNEA" in texto_mayuscula
    ):

        return extraer_numeros_linea(
            texto
        )

    # Si es exactamente uno de los números de línea
    if re.fullmatch(
        r"\d+",
        texto
    ):

        if texto in {
            str(linea)
            for linea in LINEAS_EMPRESAS.keys()
        }:

            return {texto}

    return set()


# ============================================================
# BUSCAR COLUMNAS FECHA / DOMINIO / INTERNO
# ============================================================

def identificar_encabezados(
    fila,
    columna_inicio=0
):

    resultado = {}

    for columna in range(
        columna_inicio,
        len(fila)
    ):

        valor = limpiar_texto(
            fila[columna]
        ).lower()

        if not valor:
            continue

        valor_normalizado = (
            valor
            .replace("_", "")
            .replace("-", "")
            .replace(" ", "")
        )

        if (
            "fecha" in valor_normalizado
            and "fecha" not in resultado
        ):

            resultado["fecha"] = columna

        elif (
            "dominio" in valor_normalizado
            and "dominio" not in resultado
        ):

            resultado["dominio"] = columna

        elif (
            "interno" in valor_normalizado
            and "interno" not in resultado
        ):

            resultado["interno"] = columna

    return resultado


# ============================================================
# BUSCAR ENCABEZADOS DE CADA BLOQUE
# ============================================================

def encontrar_bloques(ws):

    bloques = []

    # --------------------------------------------------------
    # Recorrer todas las celdas de la hoja
    # --------------------------------------------------------

    for fila in range(
        1,
        ws.max_row + 1
    ):

        for columna in range(
            1,
            ws.max_column + 1
        ):

            celda = ws.cell(
                fila,
                columna
            )

            valor = celda.value

            lineas = detectar_lineas_en_celda(
                valor
            )

            if not lineas:
                continue

            # ------------------------------------------------
            # Tenemos un encabezado de línea.
            #
            # Ahora buscamos el encabezado:
            #
            # fecha | dominio | interno
            #
            # debajo del mismo bloque.
            # ------------------------------------------------

            encabezados = None
            fila_encabezados = None

            for fila_siguiente in range(
                fila + 1,
                min(
                    fila + 8,
                    ws.max_row + 1
                )
            ):

                valores_fila = []

                for col in range(
                    1,
                    ws.max_column + 1
                ):

                    valores_fila.append(
                        ws.cell(
                            fila_siguiente,
                            col
                        ).value
                    )

                posibles = identificar_encabezados(
                    valores_fila,
                    max(
                        0,
                        columna - 1
                    )
                )

                if (
                    "fecha" in posibles
                    and "dominio" in posibles
                    and "interno" in posibles
                ):

                    encabezados = posibles
                    fila_encabezados = (
                        fila_siguiente
                    )

                    break

            if encabezados is None:
                continue

            # ------------------------------------------------
            # Evitar duplicados
            # ------------------------------------------------

            ya_existe = False

            for bloque in bloques:

                if (
                    bloque["fila_linea"] == fila
                    and
                    bloque["columna_linea"]
                    == columna
                ):

                    ya_existe = True
                    break

            if ya_existe:
                continue

            # ------------------------------------------------
            # Crear un bloque por cada línea detectada.
            #
            # Si el encabezado fuera:
            #
            # LINEA 63/113
            #
            # se registran ambas.
            # ------------------------------------------------

            for linea in sorted(
                lineas,
                key=lambda x: int(x)
            ):

                bloques.append(
                    {
                        "linea": linea,
                        "fila_linea": fila,
                        "columna_linea": columna,
                        "fila_encabezados":
                            fila_encabezados,
                        "col_fecha":
                            encabezados["fecha"],
                        "col_dominio":
                            encabezados["dominio"],
                        "col_interno":
                            encabezados["interno"],
                    }
                )

    # --------------------------------------------------------
    # Ordenar por posición
    # --------------------------------------------------------

    bloques.sort(
        key=lambda bloque: (
            bloque["fila_linea"],
            bloque["columna_linea"]
        )
    )

    return bloques


# ============================================================
# EXTRAER DATOS DE UN BLOQUE
# ============================================================

def extraer_datos_bloque(
    ws,
    bloque
):

    linea = bloque["linea"]

    fila_inicio = (
        bloque["fila_encabezados"]
        + 1
    )

    col_fecha = bloque["col_fecha"]
    col_dominio = bloque["col_dominio"]
    col_interno = bloque["col_interno"]

    registros = []

    # --------------------------------------------------------
    # Determinar dónde termina este bloque
    #
    # Puede terminar:
    #
    # 1. antes de otro encabezado de línea
    # 2. al encontrar muchas filas vacías
    # 3. al terminar la hoja
    # --------------------------------------------------------

    fila = fila_inicio

    filas_vacias_consecutivas = 0

    while fila <= ws.max_row:

        # ----------------------------------------------------
        # Detectar si comienza otro bloque
        # ----------------------------------------------------

        otra_linea = False

        for columna in range(
            1,
            ws.max_column + 1
        ):

            valor = ws.cell(
                fila,
                columna
            ).value

            lineas = detectar_lineas_en_celda(
                valor
            )

            if lineas:

                # Si es el encabezado del propio bloque,
                # no cortar.
                if not (
                    fila
                    == bloque["fila_linea"]
                ):

                    # Si encontramos otra línea en una fila
                    # posterior, termina el bloque.
                    if fila > fila_inicio:

                        otra_linea = True
                        break

        if otra_linea:
            break

        # ----------------------------------------------------
        # Leer las tres columnas
        # ----------------------------------------------------

        fecha = ws.cell(
            fila,
            col_fecha + 1
        ).value

        dominio = ws.cell(
            fila,
            col_dominio + 1
        ).value

        interno = ws.cell(
            fila,
            col_interno + 1
        ).value

        fecha = limpiar_texto(
            fecha
        )

        dominio = normalizar_dominio(
            dominio
        )

        interno = normalizar_interno(
            interno
        )

        # ----------------------------------------------------
        # Determinar si realmente hay un vehículo
        # ----------------------------------------------------

        tiene_datos = (
            bool(dominio)
            or bool(interno)
        )

        if tiene_datos:

            registros.append(
                {
                    "fecha": fecha,
                    "dominio": dominio,
                    "interno": interno,
                }
            )

            filas_vacias_consecutivas = 0

        else:

            filas_vacias_consecutivas += 1

            # Varias filas completamente vacías indican
            # el final del bloque.
            if filas_vacias_consecutivas >= 3:

                break

        fila += 1

    # --------------------------------------------------------
    # Crear DataFrame
    # --------------------------------------------------------

    if not registros:

        return pd.DataFrame(
            columns=[
                "fecha",
                "dominio",
                "interno"
            ]
        )

    df = pd.DataFrame(
        registros
    )

    # --------------------------------------------------------
    # Eliminar filas sin dominio e interno
    # --------------------------------------------------------

    df = df[
        (
            df["dominio"].astype(str).str.strip()
            != ""
        )
        |
        (
            df["interno"].astype(str).str.strip()
            != ""
        )
    ].copy()

    # --------------------------------------------------------
    # Agregar línea
    # --------------------------------------------------------

    df.insert(
        0,
        "linea",
        linea
    )

    return df


# ============================================================
# CONECTAR CON GOOGLE DRIVE
# ============================================================

def conectar_drive():

    contenido = None

    # --------------------------------------------------------
    # Leer Secret
    # --------------------------------------------------------

    import os

    contenido = os.environ.get(
        GOOGLE_SERVICE_ACCOUNT_JSON
    )

    if not contenido:

        raise RuntimeError(
            "No se encontró el Secret "
            "GOOGLE_SERVICE_ACCOUNT_JSON."
        )

    try:

        datos = json.loads(
            contenido
        )

    except Exception as error:

        raise RuntimeError(
            "El Secret "
            "GOOGLE_SERVICE_ACCOUNT_JSON "
            "no contiene un JSON válido."
        ) from error

    credenciales = (
        service_account
        .Credentials
        .from_service_account_info(
            datos,
            scopes=SCOPES
        )
    )

    return build(
        "drive",
        "v3",
        credentials=credenciales
    )


# ============================================================
# LISTAR ARCHIVOS DE DRIVE
# ============================================================

def listar_archivos_drive(
    drive
):

    consulta = (
        f"'{ID_CARPETA_DRIVE}' "
        "in parents "
        "and trashed = false"
    )

    respuesta = drive.files().list(
        q=consulta,
        fields=(
            "files("
            "id,"
            "name,"
            "mimeType"
            ")"
        ),
        pageSize=1000
    ).execute()

    return respuesta.get(
        "files",
        []
    )


# ============================================================
# DESCARGAR ARCHIVO
# ============================================================

def descargar_archivo(
    drive,
    archivo
):

    file_id = archivo["id"]
    mime_type = archivo["mimeType"]

    # --------------------------------------------------------
    # Google Sheets
    # --------------------------------------------------------

    if mime_type == (
        "application/vnd.google-apps.spreadsheet"
    ):

        request = drive.files().export_media(
            fileId=file_id,
            mimeType=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            )
        )

    else:

        request = drive.files().get_media(
            fileId=file_id
        )

    buffer = io.BytesIO()

    downloader = MediaIoBaseDownload(
        buffer,
        request
    )

    terminado = False

    while not terminado:

        _, terminado = downloader.next_chunk()

    buffer.seek(0)

    return buffer


# ============================================================
# PROCESAR UN ARCHIVO
# ============================================================

def procesar_archivo(
    drive,
    archivo
):

    nombre = limpiar_texto(
        archivo["name"]
    )

    print()
    print("=" * 70)

    print(
        f"ARCHIVO DRIVE: {nombre}"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # Descargar
    # --------------------------------------------------------

    try:

        contenido = descargar_archivo(
            drive,
            archivo
        )

    except Exception as error:

        print(
            f"ERROR descargando "
            f"{nombre}: {error}"
        )

        return {}

    # --------------------------------------------------------
    # Abrir Excel
    # --------------------------------------------------------

    try:

        wb = load_workbook(
            contenido,
            data_only=True
        )

    except Exception as error:

        print(
            f"ERROR abriendo "
            f"{nombre}: {error}"
        )

        return {}

    resultados = {}

    # --------------------------------------------------------
    # Recorrer hojas
    # --------------------------------------------------------

    for ws in wb.worksheets:

        print()
        print(
            f"Hoja: {ws.title}"
        )

        bloques = encontrar_bloques(
            ws
        )

        if not bloques:

            print(
                "No se encontraron bloques "
                "de líneas."
            )

            continue

        print(
            f"Bloques encontrados: "
            f"{len(bloques)}"
        )

        for bloque in bloques:

            linea = bloque["linea"]

            print()
            print(
                f"Procesando Línea {linea}..."
            )

            print(
                f"  Fila encabezado: "
                f"{bloque['fila_linea']}"
            )

            print(
                f"  Columna bloque: "
                f"{bloque['columna_linea'] + 1}"
            )

            print(
                f"  Fila columnas: "
                f"{bloque['fila_encabezados']}"
            )

            df = extraer_datos_bloque(
                ws,
                bloque
            )

            if df.empty:

                print(
                    f"  Línea {linea}: "
                    "0 controlados."
                )

                continue

            print(
                f"  Línea {linea}: "
                f"{len(df)} controlados."
            )

            if linea not in resultados:

                resultados[linea] = []

            resultados[linea].append(
                df
            )

    return resultados


# ============================================================
# UNIR Y GUARDAR CONTROLADOS
# ============================================================

def guardar_resultados(
    resultados
):

    CARPETA_CONTROLADOS.mkdir(
        parents=True,
        exist_ok=True
    )

    for linea, dataframes in resultados.items():

        if not dataframes:
            continue

        df_nuevo = pd.concat(
            dataframes,
            ignore_index=True
        )

        if df_nuevo.empty:
            continue

        archivo_salida = (
            CARPETA_CONTROLADOS
            / f"linea{linea}.csv"
        )

        # ----------------------------------------------------
        # Si ya existe información anterior,
        # conservarla y agregar lo nuevo.
        # ----------------------------------------------------

        if archivo_salida.exists():

            try:

                df_anterior = pd.read_csv(
                    archivo_salida,
                    dtype=str,
                    encoding="utf-8-sig"
                )

            except Exception:

                df_anterior = pd.DataFrame()

            if not df_anterior.empty:

                # Asegurar columnas
                for columna in [
                    "linea",
                    "fecha",
                    "dominio",
                    "interno"
                ]:

                    if columna not in df_anterior.columns:

                        df_anterior[
                            columna
                        ] = ""

                df_nuevo = pd.concat(
                    [
                        df_anterior,
                        df_nuevo
                    ],
                    ignore_index=True
                )

        # ----------------------------------------------------
        # Normalizar columnas
        # ----------------------------------------------------

        columnas_finales = [
            "linea",
            "fecha",
            "dominio",
            "interno"
        ]

        for columna in columnas_finales:

            if columna not in df_nuevo.columns:

                df_nuevo[
                    columna
                ] = ""

        df_nuevo = df_nuevo[
            columnas_finales
        ]

        # ----------------------------------------------------
        # Limpiar
        # ----------------------------------------------------

        df_nuevo["linea"] = (
            df_nuevo["linea"]
            .astype(str)
            .str.strip()
        )

        df_nuevo["dominio"] = (
            df_nuevo["dominio"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        df_nuevo["interno"] = (
            df_nuevo["interno"]
            .astype(str)
            .str.strip()
        )

        # ----------------------------------------------------
        # Eliminar duplicados
        # ----------------------------------------------------

        df_nuevo = df_nuevo.drop_duplicates(
            subset=[
                "linea",
                "dominio",
                "interno"
            ],
            keep="last"
        )

        # ----------------------------------------------------
        # Eliminar filas completamente vacías
        # ----------------------------------------------------

        df_nuevo = df_nuevo[
            (
                df_nuevo["dominio"] != ""
            )
            |
            (
                df_nuevo["interno"] != ""
            )
        ]

        # ----------------------------------------------------
        # Guardar
        # ----------------------------------------------------

        df_nuevo.to_csv(
            archivo_salida,
            index=False,
            encoding="utf-8-sig"
        )

        print()
        print(
            f"GUARDADO CONTROLADOS "
            f"LÍNEA {linea}: "
            f"{len(df_nuevo)} registros"
        )

        print(
            f"Archivo: {archivo_salida}"
        )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "LECTOR DE CONTROLADOS DESDE GOOGLE DRIVE"
    )
    print("=" * 70)

    print(
        f"Carpeta Drive: "
        f"{ID_CARPETA_DRIVE}"
    )

    print()

    # --------------------------------------------------------
    # Conectar
    # --------------------------------------------------------

    drive = conectar_drive()

    print(
        "Conexión con Google Drive: OK"
    )

    # --------------------------------------------------------
    # Listar archivos
    # --------------------------------------------------------

    archivos = listar_archivos_drive(
        drive
    )

    print(
        f"Archivos encontrados: "
        f"{len(archivos)}"
    )

    # --------------------------------------------------------
    # Procesar
    # --------------------------------------------------------

    resultados_totales = {}

    for archivo in archivos:

        nombre = limpiar_texto(
            archivo.get("name", "")
        )

        # ----------------------------------------------------
        # Solo procesar archivos que parezcan planillas
        # ----------------------------------------------------

        nombre_mayuscula = (
            nombre.upper()
        )

        extensiones_validas = (
            ".XLSX",
            ".XLS",
            ".CSV",
            ".ODS"
        )

        es_planilla = (
            nombre_mayuscula.endswith(
                extensiones_validas
            )
            or
            archivo.get("mimeType")
            == (
                "application/vnd.google-apps.spreadsheet"
            )
        )

        if not es_planilla:

            continue

        resultados = procesar_archivo(
            drive,
            archivo
        )

        # ----------------------------------------------------
        # Acumular
        # ----------------------------------------------------

        for linea, dataframes in resultados.items():

            if linea not in resultados_totales:

                resultados_totales[
                    linea
                ] = []

            resultados_totales[
                linea
            ].extend(
                dataframes
            )

    # --------------------------------------------------------
    # Guardar
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "GUARDANDO CONTROLADOS"
    )
    print("=" * 70)

    guardar_resultados(
        resultados_totales
    )

    # --------------------------------------------------------
    # Resumen
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "LECTURA DE DRIVE COMPLETADA"
    )
    print("=" * 70)

    for linea in sorted(
        resultados_totales.keys(),
        key=lambda x: int(x)
    ):

        cantidad = sum(
            len(df)
            for df in resultados_totales[
                linea
            ]
        )

        print(
            f"Línea {linea}: "
            f"{cantidad} registros nuevos leídos"
        )

    print("=" * 70)


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    main()
