# ============================================================
# ACTUALIZADOR DE PARQUES CNRT - PARQUE MÓVIL FTR
# ============================================================

from pathlib import Path
import csv
import re

import pandas as pd

from configuracion_lineas import LINEAS_EMPRESAS


# ============================================================
# CONFIGURACIÓN
# ============================================================

CARPETA_CNRT = Path("cnrt")
CARPETA_PARQUES = Path("parques")


# ============================================================
# NORMALIZAR NOMBRE DE COLUMNA
# ============================================================

def normalizar_nombre_columna(nombre):

    return (
        str(nombre)
        .strip()
        .lower()
        .replace("\ufeff", "")
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


# ============================================================
# BUSCAR COLUMNA
# ============================================================

def buscar_columna(df, posibles):

    columnas_normalizadas = {}

    for columna in df.columns:

        columnas_normalizadas[
            normalizar_nombre_columna(columna)
        ] = columna

    for posible in posibles:

        clave = normalizar_nombre_columna(
            posible
        )

        if clave in columnas_normalizadas:

            return columnas_normalizadas[clave]

    return None


# ============================================================
# NORMALIZAR EMPRESA
# ============================================================

def normalizar_empresa(valor):

    if pd.isna(valor):

        return ""

    texto = str(valor).strip()

    texto = texto.replace(
        "\ufeff",
        ""
    )

    # Ejemplo: 2077.0 -> 2077
    if re.fullmatch(
        r"\d+\.0",
        texto
    ):

        texto = texto[:-2]

    return texto


# ============================================================
# EXTRAER NÚMEROS DE LÍNEA
# ============================================================

def extraer_lineas(valor):

    """
    CNRT puede devolver valores como:

        195

    o:

        195, 2077IE, 2077OE, 2077OP1, 2077OP11

    El objetivo es detectar que la fila pertenece a la
    Línea 195 aunque existan otros datos después.

    Cada elemento separado por coma, punto y coma, barra,
    etc. se analiza individualmente.

    Ejemplos:

        195          -> 195
        2077IE       -> 2077
        2077OP1      -> 2077
        2077OP11     -> 2077

    """

    if pd.isna(valor):

        return set()

    texto = str(valor).strip()

    if not texto:

        return set()

    encontrados = set()

    # --------------------------------------------------------
    # Separar elementos
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
# DETERMINAR SI PERTENECE A UNA LÍNEA
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

    return (
        linea_buscada
        in lineas_encontradas
    )


# ============================================================
# DETECTAR SEPARADOR DEL CSV
# ============================================================

def detectar_separador(ruta):

    try:

        with open(
            ruta,
            "r",
            encoding="utf-8-sig",
            errors="replace"
        ) as archivo:

            muestra = archivo.read(
                10000
            )

        try:

            dialecto = csv.Sniffer().sniff(
                muestra,
                delimiters=",;\t|"
            )

            return dialecto.delimiter

        except Exception:

            # Los CSV de CNRT normalmente utilizan coma.
            return ","

    except Exception:

        return ","


# ============================================================
# LEER CSV CNRT
# ============================================================

def leer_csv_cnrt(ruta):

    print()
    print(
        f"Leyendo: {ruta}"
    )

    separador = detectar_separador(
        ruta
    )

    print(
        f"Separador detectado: "
        f"{repr(separador)}"
    )

    errores = []

    # --------------------------------------------------------
    # Intento 1 - UTF-8
    # --------------------------------------------------------

    try:

        df = pd.read_csv(
            ruta,
            dtype=str,
            encoding="utf-8-sig",
            sep=separador,
            engine="python",
            on_bad_lines="warn"
        )

        print(
            f"CSV leído correctamente: "
            f"{len(df)} filas"
        )

        return df

    except Exception as error:

        errores.append(
            f"UTF-8: {error}"
        )

    # --------------------------------------------------------
    # Intento 2 - Latin-1
    # --------------------------------------------------------

    try:

        df = pd.read_csv(
            ruta,
            dtype=str,
            encoding="latin-1",
            sep=separador,
            engine="python",
            on_bad_lines="warn"
        )

        print(
            f"CSV leído correctamente: "
            f"{len(df)} filas"
        )

        return df

    except Exception as error:

        errores.append(
            f"Latin-1: {error}"
        )

    # --------------------------------------------------------
    # Si no se pudo leer
    # --------------------------------------------------------

    raise RuntimeError(
        "No se pudo leer el CSV.\n"
        + "\n".join(errores)
    )


# ============================================================
# FILTRAR POR LÍNEA
# ============================================================

def filtrar_por_linea(
    df,
    linea,
    empresa_esperada,
    nombre_archivo
):

    # --------------------------------------------------------
    # Buscar columna LINEA
    # --------------------------------------------------------

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
            "no contiene una columna LINEA."
        )

        print(
            "Columnas encontradas:"
        )

        print(
            list(df.columns)
        )

        return pd.DataFrame(
            columns=df.columns
        )

    # --------------------------------------------------------
    # Buscar columna EMPRESA
    # --------------------------------------------------------

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
    # FILTRAR LÍNEA
    # --------------------------------------------------------

    print(
        f"Buscando vehículos de "
        f"Línea {linea}..."
    )

    mascara_linea = (
        df[
            columna_linea
        ]
        .apply(
            lambda valor:
                pertenece_a_linea(
                    valor,
                    linea
                )
        )
    )

    resultado = df[
        mascara_linea
    ].copy()

    print(
        f"Línea {linea}: "
        f"{len(resultado)} vehículos "
        f"encontrados."
    )

    # --------------------------------------------------------
    # FILTRAR EMPRESA
    # --------------------------------------------------------

    if columna_empresa is not None:

        empresa_esperada = (
            normalizar_empresa(
                empresa_esperada
            )
        )

        valores_empresa = (
            resultado[
                columna_empresa
            ]
            .apply(
                normalizar_empresa
            )
        )

        # ----------------------------------------------------
        # Si la empresa está vacía, conservamos la fila.
        #
        # El archivo ya fue descargado específicamente para
        # la empresa correspondiente.
        # ----------------------------------------------------

        mascara_empresa = (
            (valores_empresa == "")
            |
            (
                valores_empresa
                == empresa_esperada
            )
        )

        resultado = resultado[
            mascara_empresa
        ].copy()

    # --------------------------------------------------------
    # DEVOLVER RESULTADO
    # --------------------------------------------------------

    return resultado


# ============================================================
# PROCESAR TODAS LAS EMPRESAS
# ============================================================

def cargar_empresas():

    archivos = sorted(
        CARPETA_CNRT.glob(
            "empresa_*.csv"
        )
    )

    if not archivos:

        raise RuntimeError(
            "No se encontraron archivos "
            "empresa_*.csv dentro de cnrt."
        )

    empresas = {}

    print()
    print(
        f"Archivos CNRT encontrados: "
        f"{len(archivos)}"
    )

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

            empresas[
                empresa
            ] = df

        except Exception as error:

            print()
            print(
                "ERROR leyendo "
                f"{archivo}:"
            )

            print(
                error
            )

            # No detenemos todo el proceso por
            # un CSV defectuoso.
            continue

    return empresas


# ============================================================
# PROCESAR PARQUES
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

    print()
    print("=" * 70)
    print(
        "ACTUALIZADOR DE PARQUES CNRT"
    )
    print("=" * 70)

    empresas_data = cargar_empresas()

    if not empresas_data:

        raise RuntimeError(
            "No se pudo cargar ningún "
            "CSV de empresas."
        )

    print()
    print("=" * 70)
    print(
        "SEPARANDO VEHÍCULOS POR LÍNEA"
    )
    print("=" * 70)

    lineas_procesadas = 0

    # --------------------------------------------------------
    # LINEAS_EMPRESAS tiene:
    #
    # línea -> empresa
    #
    # Ejemplo:
    #
    # 195 -> 2077
    # --------------------------------------------------------

    for linea, empresa in sorted(
        LINEAS_EMPRESAS.items(),
        key=lambda item:
            int(item[0])
    ):

        linea = str(
            linea
        )

        empresa = str(
            empresa
        )

        print()
        print("=" * 70)

        print(
            f"LÍNEA {linea}"
        )

        print(
            f"Empresa CNRT: {empresa}"
        )

        print("=" * 70)

        # ----------------------------------------------------
        # Buscar datos de la empresa
        # ----------------------------------------------------

        df = empresas_data.get(
            empresa
        )

        if df is None:

            print(
                f"ADVERTENCIA: "
                f"no se encontró "
                f"empresa_{empresa}.csv"
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

        archivo_salida = (
            CARPETA_PARQUES
            / f"linea{linea}.csv"
        )

        # ----------------------------------------------------
        # NO SOBRESCRIBIR CON VACÍO
        # ----------------------------------------------------

        if resultado.empty:

            print()
            print(
                f"ADVERTENCIA: "
                f"Línea {linea} "
                "no encontró vehículos."
            )

            if archivo_salida.exists():

                print(
                    "Se conserva el archivo "
                    "anterior:"
                )

                print(
                    archivo_salida
                )

            else:

                print(
                    "No existe un archivo "
                    "anterior para esta línea."
                )

            continue

        # ----------------------------------------------------
        # GUARDAR
        # ----------------------------------------------------

        resultado.to_csv(
            archivo_salida,
            index=False,
            encoding="utf-8-sig"
        )

        print()
        print(
            f"OK -> {archivo_salida}"
        )

        print(
            f"Vehículos encontrados: "
            f"{len(resultado)}"
        )

        lineas_procesadas += 1

        # ----------------------------------------------------
        # DIAGNÓSTICO ESPECIAL PARA 195
        # ----------------------------------------------------

        if linea == "195":

            print()
            print("=" * 70)
            print(
                "DIAGNÓSTICO ESPECIAL - LÍNEA 195"
            )
            print("=" * 70)

            print(
                f"Empresa: {empresa}"
            )

            print(
                f"Columna LINEA utilizada: "
                f"{buscar_columna(df, ['linea', 'lineanro', 'nrolinea', 'linea_nro'])}"
            )

            print(
                f"Vehículos Línea 195: "
                f"{len(resultado)}"
            )

            columna_linea = buscar_columna(
                resultado,
                [
                    "linea",
                    "lineanro",
                    "nrolinea",
                    "linea_nro"
                ]
            )

            if columna_linea is not None:

                print()
                print(
                    "Valores de LINEA "
                    "encontrados:"
                )

                valores = (
                    resultado[
                        columna_linea
                    ]
                    .dropna()
                    .astype(str)
                    .drop_duplicates()
                    .head(30)
                    .tolist()
                )

                for valor in valores:

                    print(
                        f"  {valor}"
                    )

            print(
                "=" * 70
            )

    print()
    print("=" * 70)
    print(
        "PROCESO FINALIZADO"
    )
    print("=" * 70)

    print(
        f"Líneas procesadas correctamente: "
        f"{lineas_procesadas}"
    )

    print("=" * 70)


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    procesar()
