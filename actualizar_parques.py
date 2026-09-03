import os
import csv
import re
from playwright.sync_api import sync_playwright

# Mapeo exacto de Líneas -> Códigos de Empresa CNRT
EMPRESAS_CNRT = {
    2: "2058", 9: "2062", 10: "2008", 15: "67", 17: "2024", 22: "2022", 24: "2005",
    29: "2064", 32: "2048", 33: "972", 37: "2067", 45: "2068", 51: "2079", 53: "2054",
    56: "2013", 60: "2075", 63: "2037", 70: "2080", 74: "2079", 79: "2079", 80: "2015",
    85: "359", 91: "2013", 92: "2023", 95: "2003", 98: "2021", 100: "2042", 113: "2037",
    119: "2068", 126: "2119", 128: "2048", 129: "2033", 133: "2010", 134: "2042",
    135: "2013", 148: "2033", 154: "2068", 158: "2048", 159: "2100", 160: "2101",
    164: "2062", 168: "2105", 177: "2079", 178: "2111", 179: "9085", 180: "2099",
    195: "2077", 197: "2033"
}

OUTPUT_DIR = "parques"
URL_FORM = "https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Columnas estándar para la web (separadas por coma)
headers_salida = [
    "dominio", "empresaNro", "razonSocial", "linea", "interno", 
    "anioModelo", "chasisMarca", "carroceriaMarca", "vigenciaHasta", 
    "vigenciaHastaInspeccionTecnica", "tecnicaNro"
]

def formatear_fecha(texto):
    if not texto:
        return ""
    match_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', texto)
    if match_iso:
        a, m, d = match_iso.groups()
        return f"{d}/{m}/{a}"
    match_latino = re.search(r'\d{2}/\d{2}/\d{4}', texto)
    if match_latino:
        return match_latino.group(0)
    return texto.replace("UC:", "").strip()

def descargar_csv_empresa(page, nro_empresa):
    try:
        page.goto(URL_FORM, wait_until="networkidle", timeout=30000)
        
        selects = page.query_selector_all("select")
        if selects:
            selects[0].select_option(label="Pasajeros")
            
        inputs = page.query_selector_all("input[type='text']")
        if len(inputs) >= 2:
            inputs[1].fill(str(nro_empresa))
        elif len(inputs) == 1:
            inputs[0].fill(str(nro_empresa))

        page.click("input[type='submit'], button[type='submit']")
        page.wait_for_selector("table", timeout=20000)

        with page.expect_download(timeout=30000) as download_info:
            page.click("a:has-text('Exportar a .csv')")
        
        download = download_info.value
        temp_path = os.path.join(OUTPUT_DIR, f"temp_{nro_empresa}.csv")
        download.save_as(temp_path)

        filas_datos = []
        with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
            # Detectar separador del CSV descargado de CNRT
            linea_test = f.readline()
            sep = ";" if ";" in linea_test else ","
            f.seek(0)
            
            reader = csv.DictReader(f, delimiter=sep)
            for row in reader:
                row_norm = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
                filas_datos.append(row_norm)

        if os.path.exists(temp_path):
            os.remove(temp_path)

        return filas_datos
    except Exception as e:
        print(f"  ⚠️ Error descargando CSV de empresa {nro_empresa}: {e}")
        return []

def procesar():
    print("🚀 Descargando archivos CSV oficiales desde CNRT...")
    unidades_por_empresa = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        codigos_unicos = set(EMPRESAS_CNRT.values())
        for cod_emp in codigos_unicos:
            print(f"📡 Descargando CSV oficial Empresa N° {cod_emp}...")
            unidades_por_empresa[cod_emp] = descargar_csv_empresa(page, cod_emp)

        browser.close()

    print("\n📂 Generando archivos finales por línea...")
    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        
        todas_unidades = unidades_por_empresa.get(cod_emp, [])

        # Buscar la Razón Social real devuelta por la CNRT
        razon_social = ""
        for u in todas_unidades:
            r = u.get("razon social") or u.get("razonsocial") or u.get("empresa") or ""
            if r:
                razon_social = r
                break

        # Guardar archivo CSV estandarizado con comas
        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter=",")
            writer.writerow(headers_salida)
            
            for u in todas_unidades:
                vta_tecnica = u.get("vigencia hasta insp") or u.get("vigenciahastainspecciontecnica") or ""
                
                writer.writerow([
                    u.get("dominio") or u.get("patente") or "",
                    cod_emp,
                    razon_social,
                    str_linea,
                    u.get("interno") or "",
                    u.get("año modelo") or u.get("aniomodelo") or u.get("modelo") or "",
                    u.get("chasis marca") or u.get("chasismarca") or "",
                    u.get("carroceria marca") or u.get("carroceriamarca") or "",
                    formatear_fecha(u.get("vigencia hasta") or u.get("vigenciahasta") or ""),
                    formatear_fecha(vta_tecnica),
                    u.get("tecnica nro") or u.get("tecnicanro") or ""
                ])

        print(f"✅ linea{str_linea}.csv generado -> Empresa N° {cod_emp} | Razón Social: '{razon_social}' | Colectivos: {len(todas_unidades)}")

if __name__ == "__main__":
    procesar()
