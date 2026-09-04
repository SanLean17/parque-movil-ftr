import os
import time
from playwright.sync_api import sync_playwright

os.makedirs("descargas_raw", exist_ok=True)

# Lista completa de empresas / Razones Sociales
EMPRESAS = [
    "2062",  # General Tomás Guido S.A.
    # Agregá aquí el resto de los IDs de empresas que necesites procesar
]

def descargar_parques_cnrt():
    with sync_playwright() as p:
        # Lanzamos el navegador en modo headless
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print("Conectando con la web oficial de CNRT...")
        page.goto("https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados", wait_until="networkidle", timeout=60000)

        for emp_id in EMPRESAS:
            try:
                print(f"Iniciando descarga para la empresa ID: {emp_id}...")

                # 1. Esperar a que el formulario cargue por completo
                page.wait_for_selector("form", timeout=15000)

                # 2. Intentar seleccionar la empresa por selector genérico o valor de la opción
                # Buscamos el elemento select dentro del formulario
                select_element = page.locator("select").first
                select_element.wait_for(state="visible", timeout=10000)
                select_element.select_option(value=str(emp_id))

                # 3. Hacer clic en el botón de consulta/búsqueda
                btn_buscar = page.locator("button[type='submit'], input[type='submit'], #btnBuscar").first
                btn_buscar.click()
                
                # Esperar a que la tabla o los resultados carguen
                time.sleep(3)

                # 4. Capturar el evento de descarga al presionar 'Exportar a CSV'
                with page.expect_download(timeout=30000) as download_info:
                    # Busca el botón/enlace que contenga el texto Exportar o CSV
                    btn_exportar = page.locator("a:has-text('CSV'), button:has-text('CSV'), .btn-exportar").first
                    btn_exportar.click()

                download = download_info.value
                path_destino = os.path.join("descargas_raw", f"empresa_{emp_id}.csv")
                download.save_as(path_destino)
                print(f"-> Descarga exitosa: {path_destino}")

                time.sleep(2)

            except Exception as e:
                print(f"x Error al descargar la empresa {emp_id}: {e}")

        browser.close()

if __name__ == "__main__":
    descargar_parques_cnrt()
