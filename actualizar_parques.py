import os
import csv
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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

# Encabezados exactos que requiere el JS de tu página web
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
    return texto.strip()

def obtener_datos_empresa(page, nro_empresa):
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

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        tabla = soup.find("table")
        if not tabla:
            return []

        # Extraer encabezados de la web CNRT
        headers = [th.text.strip().lower() for th in tabla.find_all("th")]

        filas_datos = []
        for tr in tabla.find_all("tr")[1:]:
            cols = [td.text.strip() for td in tr.find_all("td")]
            if len(cols) == len(headers):
                row = dict(zip(headers, cols))
                filas_datos.append(row)

        return filas_datos
    except Exception as e:
        print(f"  ⚠️ Error consultando empresa {nro_empresa}: {e}")
        return []

def procesar():
    print("🚀 Descargando datos desde CNRT...")
    unidades_por_empresa = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        codigos_unicos = set(EMPRESAS_CNRT.values())
        for cod_emp in codigos_unicos:
            print(f"📡 Consultando CNRT Empresa N° {cod_emp}...")
            unidades_por_empresa[cod_emp] = obtener_datos_empresa(page, cod_emp)

        browser.close()

    print("\n📂 Generando archivos CSV para la web...")
    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        
        todas_unidades = unidades_por_empresa.get(cod_emp, [])
        
        # Intentar filtrar por linea si la columna existe en el CSV
        unidades_linea = []
        for u in todas_unidades:
            val_linea = str(u.get("linea", ""))
            # Si el numero de linea está en el texto de la columna 'linea'
            if str_linea in val_linea:
                unidades_linea.append(u)
        
        # Si el filtrado no encontró nada (por formato raro de la CNRT), usa el parque de la empresa
        if not unidades_linea:
            unidades_linea = todas_unidades

        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter=";")
            writer.writerow(headers_salida)
            
            for u in unidades_linea:
                # Obtener la fecha de la técnica probando nombres posibles de columna
                vta_tecnica = u.get("vigenciahastainspec") or u.get("vigenciahastainspecciontecnica") or ""
                num_tecnica = u.get("tecnicanro") or u.get("nrotecnica") or u.get("tecnica") or ""

                writer.writerow([
                    u.get("dominio", ""),
                    u.get("empresanro", cod_emp),
                    u.get("razonsocial", ""),
                    str_linea,
                    u.get("interno", ""),
                    u.get("aniomodelo", ""),
                    u.get("chasismarca", ""),
                    u.get("carroceriamarca", ""),
                    formatear_fecha(u.get("vigenciahasta", "")),
                    formatear_fecha(vta_tecnica),
                    num_tecnica
                ])

        print(f"✅ linea{str_linea}.csv generado con {len(unidades_linea)} colectivos.")

if __name__ == "__main__":
    procesar()
