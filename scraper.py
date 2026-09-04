# ============================================================
# SCRAPER CNRT - PARQUE MÓVIL FTR
# ============================================================

from pathlib import Path
import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from configuracion_lineas import EMPRESAS_CNRT


# ============================================================
# CONFIGURACIÓN
# ============================================================

URL_CNRT = (
    "https://consultapme.cnrt.gob.ar/"
    "vehiculos_habilitados"
)

CARPETA_SALIDA = Path("cnrt")


# ============================================================
# UTILIDADES
# ============================================================

def texto_limpio(valor):
    if valor is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(valor)
    ).strip()


# ============================================================
# BUSCAR Y SELECCIONAR TIPO TRANSPORTE
# ============================================================

def seleccionar_pasajeros(page):

    print(
        "Seleccionando Tipo Transporte = Pasajeros..."
    )

    selects = page.locator("select")

    cantidad_selects = selects.count()

    print(
        f"Selects encontrados en la página: "
        f"{cantidad_selects}"
    )

    # --------------------------------------------------------
    # PRIMER INTENTO:
    # buscar un select que tenga una opción cuyo texto
    # contenga "Pasajeros"
    # --------------------------------------------------------

    for i in range(cantidad_selects):

        select = selects.nth(i)

        try:

            if not select.is_visible():
                continue

            opciones = select.locator("option")

            cantidad_opciones = opciones.count()

            for j in range(cantidad_opciones):

                opcion = opciones.nth(j)

                texto = texto_limpio(
                    opcion.inner_text()
                )

                value = opcion.get_attribute(
                    "value"
                )

                if "pasajero" in texto.lower():

                    print(
                        f"Encontrada opción "
                        f"'{texto}' "
                        f"(value={value})"
                    )

                    # ----------------------------------------
                    # Seleccionar por value cuando exista
                    # ----------------------------------------

                    if value is not None:

                        try:

                            select.select_option(
                                value=value
                            )

                            print(
                                "Tipo de transporte "
                                "seleccionado correctamente."
                            )

                            return True

                        except Exception:
                            pass

                    # ----------------------------------------
                    # Segundo intento: seleccionar por label
                    # ----------------------------------------

                    try:

                        select.select_option(
                            label=texto
                        )

                        print(
                            "Tipo de transporte "
                            "seleccionado correctamente."
                        )

                        return True

                    except Exception:
                        pass

        except Exception:
            continue

    # --------------------------------------------------------
    # SEGUNDO INTENTO:
    # buscar específicamente el select relacionado con
    # "Tipo Transporte"
    # --------------------------------------------------------

    posibles_selectores = [

        'select[name*="tipo" i]',

        'select[id*="tipo" i]',

        'select[name*="transporte" i]',

        'select[id*="transporte" i]',

    ]

    for selector in posibles_selectores:

        campos = page.locator(selector)

        for i in range(campos.count()):

            select = campos.nth(i)

            try:

                if not select.is_visible():
                    continue

                opciones = select.locator("option")

                for j in range(opciones.count()):

                    opcion = opciones.nth(j)

                    texto = texto_limpio(
                        opcion.inner_text()
                    )

                    value = opcion.get_attribute(
                        "value"
                    )

                    if "pasajero" not in texto.lower():
                        continue

                    print(
                        f"Encontrada opción "
                        f"'{texto}' "
                        f"(value={value})"
                    )

                    if value:

                        try:

                            select.select_option(
                                value=value
                            )

                            print(
                                "Tipo de transporte "
                                "seleccionado correctamente."
                            )

                            return True

                        except Exception:
                            pass

                    try:

                        select.select_option(
                            label=texto
                        )

                        print(
                            "Tipo de transporte "
                            "seleccionado correctamente."
                        )

                        return True

                    except Exception:
                        pass

            except Exception:
                continue

    return False


# ============================================================
# BUSCAR CAMPO EMPRESA
# ============================================================

def buscar_campo_empresa(page):

    posibles = [

        'input[name*="habilitacion" i]',

        'input[id*="habilitacion" i]',

        'input[name*="nro" i]',

        'input[id*="nro" i]',

        'input[placeholder*="habilitacion" i]',

        'input[placeholder*="número" i]',

        'input[placeholder*="numero" i]',

        'input[type="text"]',

        'input[type="number"]',

    ]

    for selector in posibles:

        campos = page.locator(selector)

        for i in range(campos.count()):

            campo = campos.nth(i)

            try:

                if campo.is_visible():

                    return campo

            except Exception:

                continue

    return None


# ============================================================
# BUSCAR BOTÓN CONSULTA
# ============================================================

def buscar_boton_consulta(page):

    candidatos = [

        page.get_by_role(
            "button",
            name=re.compile(
                r"Enviar consulta",
                re.IGNORECASE
            )
        ),

        page.get_by_text(
            re.compile(
                r"Enviar consulta",
                re.IGNORECASE
            )
        ),

        page.locator(
            'button'
        ),

        page.locator(
            'input[type="submit"]'
        ),

    ]

    for candidato in candidatos:

        try:

            cantidad = candidato.count()

            for i in range(cantidad):

                elemento = candidato.nth(i)

                if not elemento.is_visible():
                    continue

                try:

                    texto = texto_limpio(
                        elemento.inner_text()
                    ).lower()

                except Exception:

                    texto = ""

                # Para input submit puede estar en value
                if not texto:

                    try:

                        texto = texto_limpio(
                            elemento.get_attribute("value")
                        ).lower()

                    except Exception:

                        texto = ""

                if "enviar consulta" in texto:

                    return elemento

        except Exception:

            continue

    return None


# ============================================================
# BUSCAR BOTÓN EXPORTAR
# ============================================================

def buscar_boton_exportar(page):

    candidatos = [

        page.get_by_text(
            re.compile(
                r"Exportar.*csv",
                re.IGNORECASE
            )
        ),

        page.get_by_role(
            "button",
            name=re.compile(
                r"Exportar.*csv",
                re.IGNORECASE
            )
        ),

        page.get_by_role(
            "link",
            name=re.compile(
                r"Exportar.*csv",
                re.IGNORECASE
            )
        ),

        page.locator("a"),

        page.locator("button"),

        page.locator(
            'input[type="button"]'
        ),

    ]

    for candidato in candidatos:

        try:

            cantidad = candidato.count()

            for i in range(cantidad):

                elemento = candidato.nth(i)

                if not elemento.is_visible():
                    continue

                try:

                    texto = texto_limpio(
                        elemento.inner_text()
                    ).lower()

                except Exception:

                    texto = ""

                if not texto:

                    try:

                        texto = texto_limpio(
                            elemento.get_attribute("value")
                        ).lower()

                    except Exception:

                        texto = ""

                if (
                    "exportar" in texto
                    and "csv" in texto
                ):

                    return elemento

        except Exception:

            continue

    return None


# ============================================================
# GUARDAR CAPTURA DE ERROR
# ============================================================

def guardar_captura_error(
    page,
    codigo_empresa,
    nombre
):

    try:

        page.screenshot(
            path=(
                f"cnrt_error_"
                f"{codigo_empresa}_"
                f"{nombre}.png"
            ),
            full_page=True
        )

    except Exception:

        pass


# ============================================================
# DESCARGAR UNA EMPRESA
# ============================================================

def descargar_empresa(
    page,
    codigo_empresa
):

    print()
    print("=" * 50)

    print(
        f"CONSULTANDO EMPRESA CNRT "
        f"{codigo_empresa}"
    )

    print("=" * 50)

    # --------------------------------------------------------
    # ABRIR CNRT
    # --------------------------------------------------------

    page.goto(
        URL_CNRT,
        wait_until="domcontentloaded",
        timeout=120000
    )

    try:

        page.wait_for_load_state(
            "networkidle",
            timeout=30000
        )

    except PlaywrightTimeoutError:

        pass

    page.wait_for_timeout(3000)

    # --------------------------------------------------------
    # PASAJEROS
    # --------------------------------------------------------

    if not seleccionar_pasajeros(page):

        guardar_captura_error(
            page,
            codigo_empresa,
            "pasajeros"
        )

        raise RuntimeError(
            "No se pudo seleccionar "
            "Tipo Transporte = Pasajeros."
        )

    # --------------------------------------------------------
    # EMPRESA
    # --------------------------------------------------------

    print(
        "Buscando campo "
        "Nro Habilitación CNRT..."
    )

    campo_empresa = buscar_campo_empresa(
        page
    )

    if campo_empresa is None:

        guardar_captura_error(
            page,
            codigo_empresa,
            "campo_empresa"
        )

        raise RuntimeError(
            "No se encontró el campo "
            "Nro Habilitación CNRT."
        )

    campo_empresa.fill(
        str(codigo_empresa)
    )

    print(
        f"Nro Habilitación CNRT: "
        f"{codigo_empresa}"
    )

    # --------------------------------------------------------
    # ENVIAR CONSULTA
    # --------------------------------------------------------

    boton_consulta = buscar_boton_consulta(
        page
    )

    if boton_consulta is None:

        guardar_captura_error(
            page,
            codigo_empresa,
            "boton_consulta"
        )

        raise RuntimeError(
            "No se encontró el botón "
            "Enviar consulta."
        )

    print(
        "Enviando consulta..."
    )

    boton_consulta.click()

    # --------------------------------------------------------
    # ESPERAR RESULTADOS
    # --------------------------------------------------------

    try:

        page.wait_for_load_state(
            "networkidle",
            timeout=120000
        )

    except Exception:

        # La página puede procesar la consulta
        # mediante AJAX.
        pass

    page.wait_for_timeout(7000)

    # --------------------------------------------------------
    # EXPORTACIÓN
    # --------------------------------------------------------

    print(
        "Buscando Exportar a .csv..."
    )

    boton_exportar = buscar_boton_exportar(
        page
    )

    if boton_exportar is None:

        guardar_captura_error(
            page,
            codigo_empresa,
            "exportar"
        )

        raise RuntimeError(
            "No se encontró "
            "'Exportar a .csv' "
            f"para empresa {codigo_empresa}."
        )

    # --------------------------------------------------------
    # DESCARGAR
    # --------------------------------------------------------

    print(
        "Descargando CSV..."
    )

    archivo_destino = (
        CARPETA_SALIDA
        / f"empresa_{codigo_empresa}.csv"
    )

    with page.expect_download(
        timeout=120000
    ) as descarga_info:

        boton_exportar.click()

    descarga = descarga_info.value

    descarga.save_as(
        str(archivo_destino)
    )

    # --------------------------------------------------------
    # VALIDAR
    # --------------------------------------------------------

    if not archivo_destino.exists():

        raise RuntimeError(
            f"No se creó "
            f"{archivo_destino}"
        )

    if archivo_destino.stat().st_size == 0:

        raise RuntimeError(
            f"El archivo "
            f"{archivo_destino} "
            "está vacío."
        )

    print(
        f"OK -> {archivo_destino}"
    )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    CARPETA_SALIDA.mkdir(
        parents=True,
        exist_ok=True
    )

    print()
    print("=" * 60)
    print(
        "DESCARGADOR CNRT - PARQUE MÓVIL FTR"
    )
    print("=" * 60)

    print(
        f"Empresas únicas a consultar: "
        f"{len(EMPRESAS_CNRT)}"
    )

    print()
    print("Empresas:")

    for empresa in EMPRESAS_CNRT:

        print(
            f"  - {empresa}"
        )

    print()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True,
            locale="es-AR"
        )

        page = context.new_page()

        try:

            for codigo_empresa in EMPRESAS_CNRT:

                descargar_empresa(
                    page,
                    codigo_empresa
                )

        finally:

            browser.close()

    print()
    print("=" * 60)
    print(
        "DESCARGA CNRT COMPLETADA"
    )
    print("=" * 60)


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":

    main()
