# ============================================================
# SCRAPER CNRT - PARQUE MÓVIL FTR
# ============================================================

from pathlib import Path

from playwright.sync_api import sync_playwright

from configuracion_lineas import EMPRESAS_CNRT


# ============================================================
# CONFIGURACIÓN
# ============================================================

URL_CNRT = (
    "https://consultapme.cnrt.gob.ar/"
    "consulta_vehiculos_habilitados"
)

CARPETA_SALIDA = Path("cnrt")


# ============================================================
# BUSCAR PASAJEROS
# ============================================================

def buscar_opcion_pasajeros(page):

    selects = page.locator("select")

    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            opciones = select.locator("option")

            for j in range(opciones.count()):

                texto = (
                    opciones.nth(j)
                    .inner_text()
                    .strip()
                )

                if "pasajero" in texto.lower():

                    opciones.nth(j).click()

                    print(
                        f"Tipo de transporte: {texto}"
                    )

                    return True

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
        'input[type="text"]',

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
            name="Enviar consulta"
        ),

        page.get_by_text(
            "Enviar consulta",
            exact=True
        ),

        page.locator("button"),

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

                    texto = (
                        elemento
                        .inner_text()
                        .strip()
                        .lower()
                    )

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
            "Exportar a .csv",
            exact=True
        ),

        page.get_by_text(
            "Exportar a CSV",
            exact=True
        ),

        page.get_by_role(
            "button",
            name="Exportar a .csv"
        ),

        page.get_by_role(
            "link",
            name="Exportar a .csv"
        ),

        page.get_by_text(
            "Exportar",
            exact=False
        ),

        page.locator("a"),

        page.locator("button"),

    ]

    for candidato in candidatos:

        try:

            cantidad = candidato.count()

            for i in range(cantidad):

                elemento = candidato.nth(i)

                if not elemento.is_visible():
                    continue

                try:

                    texto = (
                        elemento
                        .inner_text()
                        .strip()
                        .lower()
                    )

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
# DESCARGAR UNA EMPRESA
# ============================================================

def descargar_empresa(page, codigo_empresa):

    print()
    print("=" * 50)
    print(
        f"CONSULTANDO EMPRESA CNRT {codigo_empresa}"
    )
    print("=" * 50)

    # --------------------------------------------------------
    # ABRIR CNRT
    # --------------------------------------------------------

    page.goto(
        URL_CNRT,
        wait_until="networkidle",
        timeout=120000
    )

    page.wait_for_timeout(3000)

    # --------------------------------------------------------
    # PASAJEROS
    # --------------------------------------------------------

    print(
        "Seleccionando Tipo Transporte = Pasajeros..."
    )

    if not buscar_opcion_pasajeros(page):

        raise RuntimeError(
            "No se encontró la opción Pasajeros."
        )

    # --------------------------------------------------------
    # EMPRESA
    # --------------------------------------------------------

    campo_empresa = buscar_campo_empresa(page)

    if campo_empresa is None:

        raise RuntimeError(
            "No se encontró el campo "
            "Nro Habilitación CNRT."
        )

    campo_empresa.fill(
        str(codigo_empresa)
    )

    print(
        f"Nro Habilitación CNRT: {codigo_empresa}"
    )

    # --------------------------------------------------------
    # ENVIAR CONSULTA
    # --------------------------------------------------------

    boton_consulta = buscar_boton_consulta(page)

    if boton_consulta is None:

        raise RuntimeError(
            "No se encontró el botón "
            "Enviar consulta."
        )

    print("Enviando consulta...")

    boton_consulta.click()

    try:

        page.wait_for_load_state(
            "networkidle",
            timeout=120000
        )

    except Exception:

        # Algunas consultas son AJAX.
        pass

    page.wait_for_timeout(5000)

    # --------------------------------------------------------
    # BUSCAR EXPORTACIÓN
    # --------------------------------------------------------

    boton_exportar = buscar_boton_exportar(page)

    if boton_exportar is None:

        page.screenshot(
            path=f"cnrt_error_{codigo_empresa}.png",
            full_page=True
        )

        raise RuntimeError(
            "No se encontró 'Exportar a .csv' "
            f"para empresa {codigo_empresa}."
        )

    # --------------------------------------------------------
    # DESCARGAR
    # --------------------------------------------------------

    print("Descargando CSV...")

    with page.expect_download(
        timeout=120000
    ) as descarga_info:

        boton_exportar.click()

    descarga = descarga_info.value

    archivo_destino = (
        CARPETA_SALIDA
        / f"empresa_{codigo_empresa}.csv"
    )

    descarga.save_as(
        str(archivo_destino)
    )

    # --------------------------------------------------------
    # VALIDAR
    # --------------------------------------------------------

    if not archivo_destino.exists():

        raise RuntimeError(
            f"No se creó {archivo_destino}"
        )

    if archivo_destino.stat().st_size == 0:

        raise RuntimeError(
            f"El archivo {archivo_destino} está vacío."
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
    print("DESCARGADOR CNRT - PARQUE MÓVIL FTR")
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
    print("DESCARGA CNRT COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":

    main()
