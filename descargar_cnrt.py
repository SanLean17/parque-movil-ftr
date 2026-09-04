import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


URL_CNRT = "https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados"
EMPRESA_CNRT = "2062"

CARPETA_SALIDA = Path("cnrt")
ARCHIVO_SALIDA = CARPETA_SALIDA / "empresa_2062.csv"


def buscar_opcion_pasajeros(page):
    """
    Busca el selector correspondiente a Tipo Transporte
    y selecciona la opción Pasajeros.

    Se intenta de varias maneras para que el automatizador
    sea más resistente a pequeños cambios de la página.
    """

    selects = page.locator("select")

    for i in range(selects.count()):
        select = selects.nth(i)

        try:
            opciones = select.locator("option")
            textos = []

            for j in range(opciones.count()):
                texto = opciones.nth(j).inner_text().strip()
                textos.append(texto)

            for j, texto in enumerate(textos):
                if "pasajero" in texto.lower():
                    select.select_option(index=j)
                    print(f"Tipo de transporte seleccionado: {texto}")
                    return True

        except Exception:
            continue

    return False


def buscar_campo_empresa(page):
    """
    Busca el campo Nro Habilitación CNRT.
    """

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


def buscar_boton_consulta(page):
    """
    Busca el botón Enviar consulta.
    """

    candidatos = [
        page.get_by_role("button", name="Enviar consulta"),
        page.get_by_text("Enviar consulta", exact=True),
        page.locator("button"),
        page.locator("input[type='submit']"),
    ]

    for candidato in candidatos:

        try:
            cantidad = candidato.count()

            for i in range(cantidad):
                elemento = candidato.nth(i)

                if elemento.is_visible():
                    texto = ""

                    try:
                        texto = elemento.inner_text().strip()
                    except Exception:
                        pass

                    if (
                        "enviar consulta" in texto.lower()
                        or candidato == page.locator("input[type='submit']")
                    ):
                        return elemento

        except Exception:
            continue

    return None


def buscar_boton_exportar(page):
    """
    Busca el botón/link que contiene exactamente
    'Exportar a .csv' o una variante equivalente.
    """

    candidatos = [
        page.get_by_text("Exportar a .csv", exact=True),
        page.get_by_text("Exportar a CSV", exact=True),
        page.get_by_text("Exportar", exact=False),
        page.get_by_role("button", name="Exportar a .csv"),
        page.get_by_role("link", name="Exportar a .csv"),
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
                    texto = elemento.inner_text().strip().lower()
                except Exception:
                    texto = ""

                if "exportar" in texto and (
                    ".csv" in texto
                    or "csv" in texto
                ):
                    return elemento

        except Exception:
            continue

    return None


def main():

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

    print("========================================")
    print(" DESCARGADOR CNRT")
    print("========================================")
    print(f"URL: {URL_CNRT}")
    print(f"Empresa CNRT: {EMPRESA_CNRT}")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True,
            locale="es-AR",
        )

        page = context.new_page()

        try:

            print("Abriendo página CNRT...")

            page.goto(
                URL_CNRT,
                wait_until="networkidle",
                timeout=120000
            )

            page.wait_for_timeout(3000)

            print("Seleccionando Tipo Transporte = Pasajeros...")

            if not buscar_opcion_pasajeros(page):
                raise RuntimeError(
                    "No se pudo encontrar la opción 'Pasajeros'."
                )

            print("Buscando campo Nro Habilitación CNRT...")

            campo_empresa = buscar_campo_empresa(page)

            if campo_empresa is None:
                raise RuntimeError(
                    "No se encontró el campo Nro Habilitación CNRT."
                )

            campo_empresa.fill(EMPRESA_CNRT)

            print(
                f"Nro Habilitación CNRT ingresado: {EMPRESA_CNRT}"
            )

            boton_consulta = buscar_boton_consulta(page)

            if boton_consulta is None:
                raise RuntimeError(
                    "No se encontró el botón 'Enviar consulta'."
                )

            print("Enviando consulta...")

            boton_consulta.click()

            page.wait_for_load_state(
                "networkidle",
                timeout=120000
            )

            page.wait_for_timeout(5000)

            print("Consulta realizada.")

            # Guardamos una captura para facilitar diagnóstico
            # si CNRT cambia su página.
            page.screenshot(
                path="cnrt_debug.png",
                full_page=True
            )

            print("Buscando botón 'Exportar a .csv'...")

            boton_exportar = buscar_boton_exportar(page)

            if boton_exportar is None:

                print(
                    "No se encontró el botón de exportación."
                )

                print(
                    "Título de la página:",
                    page.title()
                )

                raise RuntimeError(
                    "CNRT no mostró el botón 'Exportar a .csv'."
                )

            print(
                "Botón de exportación encontrado."
            )

            print("Descargando CSV...")

            with page.expect_download(
                timeout=120000
            ) as descarga_info:

                boton_exportar.click()

            descarga = descarga_info.value

            print(
                "Archivo descargado:",
                descarga.suggested_filename
            )

            descarga.save_as(
                str(ARCHIVO_SALIDA)
            )

            print(
                f"CSV guardado en: {ARCHIVO_SALIDA}"
            )

            if not ARCHIVO_SALIDA.exists():
                raise RuntimeError(
                    "El CSV aparentemente se descargó, "
                    "pero no existe el archivo final."
                )

            if ARCHIVO_SALIDA.stat().st_size == 0:
                raise RuntimeError(
                    "El CSV descargado está vacío."
                )

            print(
                "Descarga CNRT finalizada correctamente."
            )

        finally:

            browser.close()


if __name__ == "__main__":
    main()
