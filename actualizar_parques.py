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

# Encabezados requeridos por tu web
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

        # Leer dinámicamente los nombres de las columnas que devuelve la CNRT
        headers = [th.text.strip() for th in tabla.find_all("th")]

        filas_datos = []
        for tr in tabla.find_all("tr")[1:]:
            cols = [td.text.strip() for td in tr.find_all("td")]
            if len(cols) == len(headers):
                # Guarda cada fila mapeando directamente 'Nombre de Columna': 'Valor'
                row = dict(zip(headers, cols))
                
                # Asignar fallback al nro de empresa si viene vacío
                if not row.get("empresaNro"):
                    row["empresaNro"] = str(nro_empresa)
                    
                filas_datos.append(row)

        return filas_datos
    except Exception as e:
        print(f"  ⚠️ Error en empresa {nro_empresa}: {e}")
        return []

def procesar():
    print("🚀 Iniciando descarga de parques CNRT...")
    unidades_por_empresa = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        codigos_unicos = set(EMPRESAS_CNRT.values())
        for cod_emp in codigos_unicos:
            print(f"📡 Consultando empresa CNRT N° {cod_emp}...")
            unidades_por_empresa[cod_emp] = obtener_datos_empresa(page, cod_emp)

        browser.close()

    print("\n📂 Mapeando campos directos al CSV...")
    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        
        todas_unidades = unidades_por_empresa.get(cod_emp, [])
        lineas_asociadas = [l for l, c in EMPRESAS_CNRT.items() if c == cod_emp]

        # Filtrar buscando el número de línea dentro del texto de la columna 'linea'
        unidades_filtradas = []
        for u in todas_unidades:
            texto_linea = u.get("linea", "")
            # Coincidencia si el número aparece aislado en el texto (ej: "LÍNEA 9", "LINEA 9")
            if re.search(r'\b' + str_linea + r'\b', texto_linea):
                unidades_filtradas.append(u)

        # Si la empresa solo tiene 1 línea registrada en tu lista, tomar todas las unidades devueltas
        if not unidades_filtradas and len(lineas_asociadas) == 1:
            unidades_filtradas = todas_unidades

        # Razón social general de respaldo
        razon_fallback = next((u.get("razonSocial", "") for u in todas_unidades if u.get("razonSocial")), "")

        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter=";")
            writer.writerow(headers_salida)
            
            for u in unidades_filtradas:
                # Buscar la inspección técnica probando los posibles nombres que devuelve la CNRT
                vta_tecnica = u.get("vigenciaHastaInspeccionTecnica") or u.get("vigenciaHastaInspec") or ""
                num_tecnica = u.get("tecnicaNro") or u.get("nroTecnica") or u.get("tecnica") or ""

                writer.writerow([
                    u.get("dominio", ""),
                    u.get("empresaNro", cod_emp),
                    u.get("razonSocial") or razon_fallback,
                    str_linea,
                    u.get("interno", ""),
                    u.get("anioModelo", ""),
                    u.get("chasisMarca", ""),
                    u.get("carroceriaMarca", ""),
                    formatear_fecha(u.get("vigenciaHasta", "")),
                    formatear_fecha(vta_tecnica),
                    num_tecnica
                ])

        print(f"✅ Línea {str_linea} (Empresa {cod_emp}): {len(unidades_filtradas)} unidades.")

if __name__ == "__main__":
    procesar()
