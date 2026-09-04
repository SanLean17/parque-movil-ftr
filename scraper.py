import os
import time
from playwright.sync_api import sync_playwright

# Crear carpeta temporal para guardar las descargas de CNRT
os.makedirs("descargas_raw", exist_ok=True)

# Listado de códigos de empresas / razones sociales a consultar en CNRT
# Agregá aquí los IDs correspondientes al selector del sitio web de la CNRT
EMPRESAS = [
    "2062",  # General Tomás Guido S.A. (Líneas 9, 164, etc.)
    # Agregar aquí otros IDs de empresas según corresponda
]

def descargar_parques_cnrt():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print("Conectando con la web oficial de CNRT...")
        page.goto("https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados")
        page.wait_for_load_state("networkidle")

        for emp_id in EMPRESAS:
            try:
                print(f"Descargando datos para la empresa ID: {emp_id}...")
                
                # Seleccionar la empresa en el desplegable
                page.select_option("select#empresa", value=emp_id)
                page.click("button#btnBuscar")
                
                # Capturar la descarga del CSV
                with page.expect_download() as download_info:
                    page.click("a.btn-exportar-csv")
                
                download = download_info.value
                path_destino = os.path.join("descargas_raw", f"empresa_{emp_id}.csv")
                download.save_as(path_destino)
                print(f"Descarga guardada en: {path_destino}")
                
                time.sleep(2)
            except Exception as e:
                print(f"Error procesando la empresa ID {emp_id}: {e}")

        browser.close()

if __name__ == "__main__":
    descargar_parques_cnrt()
