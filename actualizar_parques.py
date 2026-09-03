import os
import csv
import re
from collections import defaultdict
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

headers_salida = [
    "dominio", "empresaNro", "razonSocial", "linea", "interno", 
    "anioModelo", "chasisMarca", "carroceriaMarca", "vigenciaHasta", 
    "vigenciaHastaInspeccionTecnica", "tecnicaNro"
]

def extraer_fechas_y_tecnica(cols):
    fechas = []
    vta_num = ""
    patron_fecha = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')
    
    for idx, c in enumerate(cols):
        encontrados = patron_fecha.findall(c)
        if encontrados:
            fechas.extend(encontrados)
        elif idx >= 8 and c.strip() and not c.strip().startswith("20"):
            vta_num = c.strip()

    hab = fechas[0] if len(fechas) > 0 else ""
    vta_vig = fechas[1] if len(fechas) > 1 else ""
    
    if not vta_num and len(cols) > 9:
        ultimo = cols[-1].strip()
        if ultimo and not patron_fecha.search(ultimo):
            vta_num = ultimo

    return hab, vta_vig, vta_num

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

        filas_datos = []
        for tr in tabla.find_all("tr")[1:]:
            cols = [td.text.strip() for td in tr.find_all("td")]
            if len(cols) >= 5:
                dom = cols[0] if len(cols) > 0 else ""
                inte = cols[1] if len(cols) > 1 else ""
                
                # Extraer el número/nombre de la línea desde la celda de la CNRT (suele estar en cols[2] o cols[4])
                linea_raw = cols[2] if len(cols) > 2 else ""
                # Extraer solo los números de la línea (ej: "Línea 45" -> "45")
                linea_num_match = re.search(r'\d+', linea_raw)
                linea_extraida = linea_num_match.group(0) if linea_num_match else linea_raw

                mod = cols[3] if len(cols) > 3 else ""
                emp = str(nro_empresa)
                raz = cols[7] if len(cols) > 7 else ""

                hab, vta_vig, vta_num = extraer_fechas_y_tecnica(cols)

                filas_datos.append({
                    "dominio": dom,
                    "empresaNro": emp,
                    "razonSocial": raz,
                    "linea": linea_extraida,
                    "interno": inte,
                    "anioModelo": mod,
                    "chasisMarca": "",
                    "carroceriaMarca": "",
                    "vigenciaHasta": hab,
                    "vigenciaHastaInspeccionTecnica": vta_vig,
                    "tecnicaNro": vta_num
                })
        return filas_datos
    except Exception as e:
        print(f"  ⚠️ Error en empresa {nro_empresa}: {e}")
        return []

def procesar():
    print("🚀 Iniciando descarga de parques CNRT...")
    
    # Agrupador para evitar hacer múltiples consultas a la misma empresa de la CNRT
    empresas_procesadas = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Consultar cada código de empresa único
        codigos_unicos = set(EMPRESAS_CNRT.values())
        unidades_por_empresa = {}

        for cod_emp in codigos_unicos:
            print(f"📡 Consultando empresa CNRT N° {cod_emp}...")
            unidades_por_empresa[cod_emp] = obtener_datos_empresa(page, cod_emp)

        browser.close()

    # 2. Filtrar y separar por línea específica
    print("\n📂 Filtrando y generando archivos CSV por línea...")
    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        
        todas_unidades = unidades_por_empresa.get(cod_emp, [])
        
        # Filtrar unidades que pertenezcan exactamente a esta línea
        unidades_filtradas = [
            u for u in todas_unidades 
            if u["linea"] == str_linea or u["linea"] == f"0{str_linea}" or not u["linea"]
        ]

        # Si el filtro por coincidencia estricta devuelve 0 pero la empresa maneja 1 sola línea, asignarla
        lineas_de_esta_empresa = [str(l) for l, c in EMPRESAS_CNRT.items() if c == cod_emp]
        if len(lineas_de_esta_empresa) == 1 and not unidades_filtradas:
            unidades_filtradas = todas_unidades

        # Escribir el CSV con el total real de la línea
        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter=";")
            writer.writerow(headers_salida)
            
            for u in unidades_filtradas:
                writer.writerow([
                    u["dominio"], u["empresaNro"], u["razonSocial"], str_linea,
                    u["interno"], u["anioModelo"], u["chasisMarca"], u["carroceriaMarca"],
                    u["vigenciaHasta"], u["vigenciaHastaInspeccionTecnica"], u["tecnicaNro"]
                ])

        print(f"✅ Línea {str_linea} (Empresa {cod_emp}): {len(unidades_filtradas)} unidades (de {len(todas_unidades)} totales de la empresa).")

if __name__ == "__main__":
    procesar()
