import os
import time
from playwright.sync_api import sync_playwright

# Crear carpeta temporal de descargas
os.makedirs("descargas_raw", exist_ok=True)

# Listado de IDs o nombres de empresas/líneas a consultar en el sitio
# Agregá acá los identificadores según las opciones del select de la CNRT
EMPRESAS = [
    "2062", # Ejemplo: General Tomás Guido S.A.
    # Agregar el resto de los IDs de las empresas de tu interés
]

def descargar_parques_cnrt():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print("Navegando a la web de la CNRT...")
        page.goto("https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados")
        page.wait_for_load_state("networkidle")

        for emp_id in EMPRESAS:
            try:
                print(f"Procesando empresa ID: {emp_id}")
                # Seleccionar la empresa en el formulario (ajustar el selector si varía)
                page.select_option("select#empresa", value=emp_id)
                page.click("button#btnBuscar") # Ajustar ID del botón si aplica
                
                # Esperar y capturar la descarga del CSV/Excel
                with page.expect_download() as download_info:
                    page.click("a.btn-exportar-csv") # Ajustar el selector de exportación
                
                download = download_info.value
                path_destino = os.path.join("descargas_raw", f"empresa_{emp_id}.csv")
                download.save_as(path_destino)
                print(f"Guardado exitosamente: {path_destino}")
                
                time.sleep(2)
            except Exception as e:
                print(f"Error descargando empresa {emp_id}: {e}")

        browser.close()

if __name__ == "__main__":
    descargar_parques_cnrt()
