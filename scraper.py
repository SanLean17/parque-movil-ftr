import os
import time
from playwright.sync_api import sync_playwright

# Directorio de descargas temporales
DIR_DESCARGAS = "descargas_raw"
os.makedirs(DIR_DESCARGAS, exist_ok=True)

# Mapeo completo de tus empresas (IDs únicos extraídos de tu lista)
# 2058 (L2), 2062 (L9, L164), 2008 (L10), 67 (L15), 2024 (L17), 2022 (L22), 
# 2005 (L24), 2064 (L29), 2048 (L32, L128, L158), 972 (L33), 2067 (L37), 
# 2068 (L45, L119, L154), 2079 (L51, L74, L79, L177), 2054 (L53), 2013 (L56, L91, L135), 
# 2075 (L60), 2037 (L63, L113), 2080 (L70), 2015 (L80), 359 (L85), 2023 (L92), 
# 2003 (L95), 2021 (L98), 2042 (L100, L134), 2119 (L126), 2033 (L129, L148, L197), 
# 2010 (L133), 2100 (L159), 2101 (L160), 2105 (L168), 2111 (L178), 9085 (L179), 
# 2099 (L180), 2077 (L195)
EMPRESAS_IDS = list(set([
    "2058", "2062", "2008", "67", "2024", "2022", "2005", "2064", "2048", "972", 
    "2067", "2068", "2079", "2054", "2013", "2075", "2037", "2080", "2015", "359", 
    "2023", "2003", "2021", "2042", "2119", "2033", "2010", "2100", "2101", "2105", 
    "2111", "9085", "2099", "2077"
]))

URL_CNRT = "https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados"

def ejecutar_scraper():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print(f"Navegando a {URL_CNRT}...")
        try:
            page.goto(URL_CNRT, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Error al cargar la página principal: {e}")
            browser.close()
            return

        descargas_exitosas = 0

        for idx, emp_id in enumerate(EMPRESAS_IDS, 1):
            print(f"[{idx}/{len(EMPRESAS_IDS)}] Procesando empresa ID: {emp_id}...")
            
            try:
                # 1. Esperar a que el selector de empresa esté visible
                # El formulario de CNRT usa select[name="empresa_id"] o similar
                selector_empresa = 'select[name="empresa_id"], select#empresa_id, select'
                page.wait_for_selector(selector_empresa, timeout=10000)

                # 2. Seleccionar la empresa por su Value ID
                page.select_option(selector_empresa, value=str(emp_id))
                time.sleep(1)

                # 3. Hacer clic en el botón Buscar/Consultar
                # CNRT utiliza un botón submit principal dentro del formulario
                btn_buscar = page.locator('button[type="submit"], input[type="submit"], .btn-primary').first
                btn_buscar.click()

                # Esperar a que renderice la tabla de resultados
                page.wait_for_load_state("networkidle", timeout=15000)

                # 4. Capturar evento de descarga del CSV
                # Busca enlaces o botones de exportación CSV
                btn_exportar = page.locator('a:has-text("CSV"), a:has-text("Exportar"), .btn-success, .btn-exportar').first
                
                with page.expect_download(timeout=15000) as download_info:
                    btn_exportar.click()

                download = download_info.value
                path_destino = os.path.join(DIR_DESCARGAS, f"empresa_{emp_id}.csv")
                download.save_as(path_destino)
                
                print(f"   -> Descargado con éxito: {path_destino}")
                descargas_exitosas += 1

            except Exception as e:
                print(f"   x Falló la descarga para empresa {emp_id}: {e}")

            # Pausa para no saturar los servidores de CNRT
            time.sleep(2)

        browser.close()
        print(f"\nProceso finalizado. Total descargados: {descargas_exitosas}/{len(EMPRESAS_IDS)}")

if __name__ == "__main__":
    ejecutar_scraper()
