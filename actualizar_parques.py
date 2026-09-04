from pathlib import Path
import pandas as pd

from configuracion_lineas import LINEAS_EMPRESAS


# ============================================================
# CARPETAS
# ============================================================

CARPETA_CNRT = Path("cnrt")
CARPETA_PARQUES = Path("parques")
CARPETA_CONTROLADOS = Path("controlados")


CARPETA_CNRT.mkdir(
    parents=True,
    exist_ok=True
)

CARPETA_PARQUES.mkdir(
    parents=True,
    exist_ok=True
)

CARPETA_CONTROLADOS.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# FUNCIONES DE COLUMNAS
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

    buscadas = {
        normalizar_nombre_columna(nombre)
        for nombre in nombres
    }

    for columna in df.columns:

        normalizada = (
            normalizar_nombre_columna(
                columna
            )
        )

        if normalizada in buscadas:

            return columna

    return None


def obtener_columna_linea(df):

    return obtener_columna(
        df,
        [
            "linea",
            "lineanro",
            "nrolinea",
            "linea_nro",
        ]
    )


def obtener_columna_empresa(df):

    return obtener_columna(
        df,
        [
            "empresaNro",
            "empresa",
            "nroEmpresa",
            "nroHabilitacionCNRT",
        ]
    )


def obtener_columna_dominio(df):

    return obtener_columna(
        df,
        [
            "dominio",
            "patente",
            "dominio_vehiculo",
        ]
    )


# ============================================================
# NORMALIZACIÓN
# ============================================================

def normalizar_numero(valor):

    if pd.isna(valor):

        return ""

    texto = str(valor).strip()

    if not texto:

        return ""

    try:

        numero = float(texto)

        if numero.is_integer():

            return str(int(numero))

    except Exception:

        pass

    return texto


def normalizar_dominio(valor):

    if pd.isna(valor):

        return ""

    return (
        str(valor)
        .strip()
        .upper()
    )


# ============================================================
# LEER CSV
# ============================================================

def leer_csv(path):

    for separador in [";", ","]:

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

            continue

    raise RuntimeError(
        f"No se pudo leer el CSV: {path}"
    )


# ============================================================
# OBTENER ARCHIVOS CNRT
# ============================================================

def obtener_archivos_cnrt():

    archivos = sorted(
        CARPETA_CNRT.glob(
            "empresa_*.csv"
        )
    )

    return archivos


# ============================================================
# CARGAR TODAS LAS DESCARGAS
# ============================================================

def cargar_datos_cnrt():

    archivos = obtener_archivos_cnrt()

    if not archivos:

        raise RuntimeError(
            "No hay archivos CNRT descargados."
        )

    dfs = []

    for archivo in archivos:

        print(
            f"Leyendo: {archivo}"
        )

        df = leer_csv(archivo)

        if df.empty:

            print(
                f"ADVERTENCIA: {archivo} está vacío."
            )

            continue

        dfs.append(df)

    if not dfs:

        raise RuntimeError(
            "Todos los CSV de CNRT están vacíos."
        )

    return pd.concat(
        dfs,
        ignore_index=True
    )


# ============================================================
# FILTRAR POR CONFIGURACIÓN
# ============================================================

def filtrar_lineas_configuradas(df):

    columna_empresa = obtener_columna_empresa(
        df
    )

    columna_linea = obtener_columna_linea(
        df
    )

    if columna_empresa is None:

        raise RuntimeError(
            "El CSV de CNRT no tiene columna "
            "empresaNro."
        )

    if columna_linea is None:

        raise RuntimeError(
            "El CSV de CNRT no tiene columna "
            "linea."
        )

    trabajo = df.copy()

    trabajo["_empresa"] = (
        trabajo[columna_empresa]
        .fillna("")
        .apply(normalizar_numero)
    )

    trabajo["_linea"] = (
        trabajo[columna_linea]
        .fillna("")
        .apply(normalizar_numero)
    )

    # --------------------------------------------------------
    # CREAR PARES VÁLIDOS
    # --------------------------------------------------------

    pares_validos = {
        (
            str(empresa),
            str(linea)
        )
        for linea, empresa
        in LINEAS_EMPRESAS.items()
    }

    trabajo["_par"] = list(
        zip(
            trabajo["_empresa"],
            trabajo["_linea"]
        )
    )

    filtrado = trabajo[
        trabajo["_par"].isin(
            pares_validos
        )
    ].copy()

    # --------------------------------------------------------
    # ELIMINAR COLUMNAS AUXILIARES
    # --------------------------------------------------------

    filtrado.drop(
        columns=[
            "_empresa",
            "_linea",
            "_par"
        ],
        inplace=True
    )

    return filtrado


# ============================================================
# MOSTRAR RESUMEN
# ============================================================

def mostrar_resumen(df):

    columna_empresa = obtener_columna_empresa(
        df
    )

    columna_linea = obtener_columna_linea(
        df
    )

    print()
    print("========================================")
    print(" RESUMEN DE VEHÍCULOS")
    print("========================================")

    for linea, empresa in sorted(
        LINEAS_EMPRESAS.items(),
        key=lambda x: int(x[0])
    ):

        datos = df[
            (
                df[columna_empresa]
                .fillna("")
                .apply(normalizar_numero)
                == normalizar_numero(empresa)
            )
            &
            (
                df[columna_linea]
                .fillna("")
                .apply(normalizar_numero)
                == normalizar_numero(linea)
            )
        ]

        print(
            f"Línea {linea:>3} "
            f"(empresa {empresa}): "
            f"{len(datos)} vehículos"
        )


# ============================================================
# GUARDAR PARQUES
# ============================================================

def guardar_parques(df):

    columna_empresa = obtener_columna_empresa(
        df
    )

    columna_linea = obtener_columna_linea(
        df
    )

    if columna_empresa is None:

        raise RuntimeError(
            "No existe columna empresa."
        )

    if columna_linea is None:

        raise RuntimeError(
            "No existe columna linea."
        )

    for linea, empresa in sorted(
        LINEAS_EMPRESAS.items(),
        key=lambda x: int(x[0])
    ):

        empresa_normalizada = (
            normalizar_numero(empresa)
        )

        linea_normalizada = (
            normalizar_numero(linea)
        )

        datos = df[
            (
                df[columna_empresa]
                .fillna("")
                .apply(normalizar_numero)
                == empresa_normalizada
            )
            &
            (
                df[columna_linea]
                .fillna("")
                .apply(normalizar_numero)
                == linea_normalizada
            )
        ].copy()

        if datos.empty:

            print(
                f"ADVERTENCIA: Línea {linea} "
                f"no devolvió vehículos."
            )

            print(
                "NO se reemplaza su CSV anterior."
            )

            continue

        archivo = (
            CARPETA_PARQUES
            / f"linea{linea}.csv"
        )

        datos.to_csv(
            archivo,
            index=False,
            encoding="utf-8-sig",
            sep=";"
        )

        print(
            f"Línea {linea}: "
            f"{len(datos)} vehículos → {archivo}"
        )


# ============================================================
# ACTUALIZAR CONTROLADOS
# ============================================================

def actualizar_controlados(df):

    columna_linea = obtener_columna_linea(
        df
    )

    columna_dominio = obtener_columna_dominio(
        df
    )

    if columna_linea is None:

        raise RuntimeError(
            "No existe columna linea."
        )

    if columna_dominio is None:

        raise RuntimeError(
            "No existe columna dominio."
        )

    print()
    print("========================================")
    print(" ACTUALIZANDO CONTROLADOS")
    print("========================================")

    for linea, empresa in sorted(
        LINEAS_EMPRESAS.items(),
        key=lambda x: int(x[0])
    ):

        archivo_controlados = (
            CARPETA_CONTROLADOS
            / f"linea{linea}.csv"
        )

        if not archivo_controlados.exists():

            continue

        try:

            controlados = leer_csv(
                archivo_controlados
            )

        except Exception as e:

            print(
                f"Error leyendo {archivo_controlados}: "
                f"{e}"
            )

            continue

        if controlados.empty:

            continue

        columna_dom_controlados = (
            obtener_columna_dominio(
                controlados
            )
        )

        if columna_dom_controlados is None:

            print(
                f"No se encontró dominio en "
                f"{archivo_controlados}"
            )

            continue

        parque_linea = df[
            (
                df[columna_linea]
                .fillna("")
                .apply(normalizar_numero)
                == normalizar_numero(linea)
            )
            &
            (
                df[
                    obtener_columna_empresa(df)
                ]
                .fillna("")
                .apply(normalizar_numero)
                == normalizar_numero(empresa)
            )
        ]

        dominios_actuales = {
            normalizar_dominio(valor)
            for valor
            in parque_linea[
                columna_dominio
            ]
        }

        controlados["_dominio_temp"] = (
            controlados[
                columna_dom_controlados
            ]
            .apply(normalizar_dominio)
        )

        controlados = controlados[
            controlados[
                "_dominio_temp"
            ].isin(
                dominios_actuales
            )
        ].copy()

        controlados.drop(
            columns=[
                "_dominio_temp"
            ],
            inplace=True
        )

        controlados.to_csv(
            archivo_controlados,
            index=False,
            encoding="utf-8-sig",
            sep=";"
        )

        print(
            f"Línea {linea}: "
            f"{len(controlados)} controlados conservados."
        )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    print()
    print("========================================")
    print(" ACTUALIZADOR DE PARQUES FTR")
    print("========================================")

    # --------------------------------------------------------
    # CARGAR CNRT
    # --------------------------------------------------------

    df_cnrt = cargar_datos_cnrt()

    print()
    print(
        f"Registros totales descargados: "
        f"{len(df_cnrt)}"
    )

    # --------------------------------------------------------
    # FILTRAR
    # --------------------------------------------------------

    df_filtrado = (
        filtrar_lineas_configuradas(
            df_cnrt
        )
    )

    print(
        f"Registros correspondientes a "
        f"las líneas de la web: "
        f"{len(df_filtrado)}"
    )

    # --------------------------------------------------------
    # RESUMEN
    # --------------------------------------------------------

    mostrar_resumen(
        df_filtrado
    )

    # --------------------------------------------------------
    # GUARDAR PARQUES
    # --------------------------------------------------------

    guardar_parques(
        df_filtrado
    )

    # --------------------------------------------------------
    # CONTROLADOS
    # --------------------------------------------------------

    actualizar_controlados(
        df_filtrado
    )

    print()
    print("========================================")
    print(" ACTUALIZACIÓN COMPLETADA")
    print("========================================")


if __name__ == "__main__":

    main()
