# ============================================================
# ACTUALIZAR PARQUES POR LÍNEA
# ============================================================

from pathlib import Path
import pandas as pd
import re

from configuracion_lineas import LINEAS_EMPRESAS


# ------------------------------------------------------------
# CARPETAS
# ------------------------------------------------------------

CARPETA_CNRT = Path("cnrt")
CARPETA_PARQUES = Path("parques")

CARPETA_CNRT.mkdir(exist_ok=True)
CARPETA_PARQUES.mkdir(exist_ok=True)


# ------------------------------------------------------------
# NORMALIZACIÓN DE COLUMNAS
# ------------------------------------------------------------

def normalizar_nombre_columna(nombre):
    """
    Convierte nombres de columnas a una forma comparable.
    """

    nombre = str(nombre).strip().lower()

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
        nombre = nombre.replace(viejo, nuevo)

    nombre = re.sub(r"[^a-z0-9]", "", nombre)

    return nombre


def encontrar_columna(df, posibles):
    """
    Busca una columna aunque CNRT cambie mayúsculas,
    espacios o acentos.
    """

    mapa = {
        normalizar_nombre_columna(col): col
        for col in df.columns
    }

    for posible in posibles:
        clave = normalizar_nombre_columna(posible)

        if clave in mapa:
            return mapa[clave]

    return None


# ------------------------------------------------------------
# EXTRAER LÍNEAS
# ------------------------------------------------------------

def extraer_numeros_linea(valor):
    """
    Extrae números de una celda de línea.

    Ejemplos:

    '195'
        -> [195]

    '195, 2077IE, 2077OE, 2077OP1'
        -> [195]

    '45, 70, 119'
        -> [45, 70, 119]

    '51/74/79/164/177'
        -> [51, 74, 79, 164, 177]

    La idea es quedarse con los identificadores numéricos
    de las líneas y NO confundir los números internos de
    una empresa con líneas.
    """

    if pd.isna(valor):
        return []

    texto = str(valor).strip()

    if not texto:
        return []

    # Separadores habituales.
    partes = re.split(r"[,;/|]+", texto)

    resultado = []

    for parte in partes:

        parte = parte.strip()

        if not parte:
            continue

        # Si el elemento empieza directamente con números,
        # tomamos ese número.
        #
        # Ejemplo:
        # 195       -> 195
        # 2077IE    -> 2077
        # 2077OP11  -> 2077
        #
        # PERO posteriormente solo aceptaremos números que
        # estén dentro de LINEAS_EMPRESAS.
        match = re.match(r"^(\d+)", parte)

        if match:
            numero = int(match.group(1))

            if numero in LINEAS_EMPRESAS:
                resultado.append(numero)

    # Eliminar duplicados conservando orden.
    return list(dict.fromkeys(resultado))


# ------------------------------------------------------------
# OBTENER LÍNEA PRINCIPAL
# ------------------------------------------------------------

def obtener_lineas_de_fila(valor):
    """
    Devuelve las líneas configuradas encontradas en la celda.
    """

    return extraer_numeros_linea(valor)


# ------------------------------------------------------------
# LEER TODOS LOS CSV CNRT
# ------------------------------------------------------------

def cargar_datos_cnrt():
    archivos = sorted(CARPETA_CNRT.glob("empresa_*.csv"))

    if not archivos:
        print("ERROR: no se encontraron CSV en la carpeta cnrt/")
        return pd.DataFrame()

    datos = []

    for archivo in archivos:

        print(f"Leyendo: {archivo}")

        try:
            df = pd.read_csv(
                archivo,
                dtype=str,
                keep_default_na=False,
                encoding="utf-8-sig",
            )
        except UnicodeDecodeError:
            df = pd.read_csv(
                archivo,
                dtype=str,
                keep_default_na=False,
                encoding="latin-1",
            )
        except Exception as e:
            print(f"ERROR leyendo {archivo}: {e}")
            continue

        if df.empty:
            print(f"  -> vacío")
            continue

        # Empresa obtenida del nombre:
        #
        # empresa_2077.csv
        #
        match = re.search(r"empresa_(\d+)", archivo.stem)

        if match:
            empresa = int(match.group(1))
            df["_empresa_archivo"] = str(empresa)

        datos.append(df)

    if not datos:
        return pd.DataFrame()

    resultado = pd.concat(
        datos,
        ignore_index=True,
        sort=False,
    )

    return resultado


# ------------------------------------------------------------
# FILTRAR POR LÍNEA
# ------------------------------------------------------------

def filtrar_por_linea(df, linea):
    """
    Devuelve únicamente los vehículos que pertenecen a la línea
    indicada y a su empresa correspondiente.

    IMPORTANTE:
    No existe fallback que devuelva toda la empresa.
    """

    linea = int(linea)

    empresa_esperada = LINEAS_EMPRESAS.get(linea)

    if empresa_esperada is None:
        print(f"Línea {linea}: no está configurada.")
        return pd.DataFrame(columns=df.columns)

    if df.empty:
        return pd.DataFrame(columns=df.columns)

    columna_linea = encontrar_columna(
        df,
        [
            "linea",
            "línea",
            "lineanro",
            "nrolinea",
            "nro_linea",
        ],
    )

    if columna_linea is None:
        print(
            f"ERROR: no se encontró columna 'linea' "
            f"para la línea {linea}."
        )

        return pd.DataFrame(columns=df.columns)

    columna_empresa = encontrar_columna(
        df,
        [
            "empresaNro",
            "empresa_nro",
            "empresa",
            "nroempresa",
            "nro_empresa",
        ],
    )

    filas_validas = []

    for _, fila in df.iterrows():

        # ----------------------------------------------------
        # COMPROBAR EMPRESA
        # ----------------------------------------------------

        if columna_empresa:

            valor_empresa = str(
                fila.get(columna_empresa, "")
            ).strip()

            # Si la empresa no coincide, descartamos.
            if valor_empresa:

                numeros_empresa = re.findall(
                    r"\d+",
                    valor_empresa
                )

                if numeros_empresa:

                    if str(empresa_esperada) not in numeros_empresa:
                        continue

        else:

            # Si no existe columna empresa, usamos el nombre
            # del archivo como respaldo.
            empresa_archivo = str(
                fila.get("_empresa_archivo", "")
            ).strip()

            if empresa_archivo:
                if empresa_archivo != str(empresa_esperada):
                    continue

        # ----------------------------------------------------
        # COMPROBAR LÍNEA
        # ----------------------------------------------------

        valor_linea = fila.get(
            columna_linea,
            ""
        )

        lineas_encontradas = obtener_lineas_de_fila(
            valor_linea
        )

        # La línea configurada debe aparecer explícitamente.
        if linea not in lineas_encontradas:
            continue

        filas_validas.append(fila)

    if not filas_validas:
        return pd.DataFrame(columns=df.columns)

    resultado = pd.DataFrame(
        filas_validas,
        columns=df.columns,
    )

    return resultado


# ------------------------------------------------------------
# LIMPIAR COLUMNAS INTERNAS
# ------------------------------------------------------------

def limpiar_dataframe(df):
    columnas_eliminar = [
        "_empresa_archivo",
    ]

    columnas_existentes = [
        columna
        for columna in columnas_eliminar
        if columna in df.columns
    ]

    if columnas_existentes:
        df = df.drop(
            columns=columnas_existentes
        )

    return df


# ------------------------------------------------------------
# GUARDAR
# ------------------------------------------------------------

def guardar_linea(df, linea):
    """

    Guarda:

        parques/lineaXXX.csv

    """

    archivo = CARPETA_PARQUES / f"linea{linea}.csv"

    df = limpiar_dataframe(df)

    # Si no encontramos vehículos, NO sobrescribimos un archivo
    # existente con vacío.
    #
    # Esto evita que una falla temporal de CNRT destruya
    # los datos anteriores.
    if df.empty:

        print(
            f"Línea {linea}: 0 vehículos encontrados."
        )

        if archivo.exists():
            print(
                f"  -> Se conserva {archivo} "
                f"porque ya existe."
            )
        else:
            print(
                f"  -> No se crea archivo vacío."
            )

        return

    df.to_csv(
        archivo,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"Línea {linea}: {len(df)} vehículos -> {archivo}"
    )


# ------------------------------------------------------------
# DIAGNÓSTICO
# ------------------------------------------------------------

def diagnostico_linea_195(df):
    """
    Diagnóstico específico de la Línea 195.

    Sirve para que en los logs de GitHub Actions podamos
    comprobar qué está entregando CNRT.
    """

    linea = 195

    print("")
    print("=" * 60)
    print("DIAGNÓSTICO LÍNEA 195")
    print("=" * 60)

    columna_linea = encontrar_columna(
        df,
        [
            "linea",
            "línea",
            "lineanro",
            "nrolinea",
            "nro_linea",
        ],
    )

    if columna_linea is None:
        print("No se encontró columna linea.")
        print("=" * 60)
        return

    columna_empresa = encontrar_columna(
        df,
        [
            "empresaNro",
            "empresa_nro",
            "empresa",
            "nroempresa",
            "nro_empresa",
        ],
    )

    if columna_empresa:

        df_195 = df[
            df[columna_empresa].astype(str).str.strip()
            == "2077"
        ]

    else:

        df_195 = df.copy()

    print(
        f"Filas de empresa 2077: {len(df_195)}"
    )

    contador = 0

    for _, fila in df_195.iterrows():

        valor = fila.get(
            columna_linea,
            ""
        )

        lineas = extraer_numeros_linea(valor)

        if 195 in lineas:

            contador += 1

            if contador <= 10:

                print(
                    f"Ejemplo {contador}:"
                )

                print(
                    f"  linea CNRT = {valor}"
                )

                print(
                    f"  líneas detectadas = {lineas}"
                )

    print(
        f"Vehículos donde se detectó línea 195: "
        f"{contador}"
    )

    print("=" * 60)
    print("")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():

    print("")
    print("=" * 60)
    print("ACTUALIZADOR DE PARQUES CNRT")
    print("=" * 60)
    print("")

    df = cargar_datos_cnrt()

    if df.empty:
        print(
            "ERROR: no se pudieron cargar datos CNRT."
        )
        return

    print(
        f"Total de registros CNRT cargados: {len(df)}"
    )

    # Diagnóstico específico para 195.
    diagnostico_linea_195(df)

    # --------------------------------------------------------
    # GENERAR CADA LÍNEA
    # --------------------------------------------------------

    for linea in sorted(LINEAS_EMPRESAS):

        resultado = filtrar_por_linea(
            df,
            linea,
        )

        guardar_linea(
            resultado,
            linea,
        )

    print("")
    print("=" * 60)
    print("PROCESO TERMINADO")
    print("=" * 60)
    print("")


if __name__ == "__main__":
    main()
