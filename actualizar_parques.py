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
            if len(cols) >= 4:
                dom = cols[0] if len(cols) > 0 else ""
                inte = cols[1] if len(cols) > 1 else ""
                
                # Buscar dinámicamente la celda que contiene la línea y la razón social
                linea_raw = ""
                razon_social = ""
                
                for c in cols:
                    if "LINEA" in c.upper() or "LÍNEA" in c.upper():
                        linea_raw = c
                    elif len(c) > 5 and not c.isdigit() and "/" not in c and not razon_social:
                        razon_social = c

                # Extraer solo el número entero de la línea para normalizar (ej. "LÍNEA 009" -> 9)
                match_num = re.search(r'\d+', linea_raw)
                linea_num = int(match_num.group(0)) if match_num else None

                mod = cols[3] if len(cols) > 3 and cols[3].isdigit() else ""
                hab, vta_vig, vta_num = extraer_fechas_y_tecnica(cols)

                filas_datos.append({
                    "dominio": dom,
                    "empresaNro": str(nro_empresa),
                    "razonSocial": razon_social,
                    "linea_num": linea_num,
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
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        codigos_unicos = set(EMPRESAS_CNRT.values())
        unidades_por_empresa = {}

        for cod_emp in codigos_unicos:
            print(f"📡 Consultando empresa CNRT N° {cod_emp}...")
            unidades_por_empresa[cod_emp] = obtener_datos_empresa(page, cod_emp)

        browser.close()

    print("\n📂 Filtrando y generando archivos CSV por línea...")
    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        int_linea = int(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        
        todas_unidades = unidades_por_empresa.get(cod_emp, [])
        
        # Filtro flexible por número entero
        unidades_filtradas = [
            u for u in todas_unidades 
            if u["linea_num"] == int_linea
        ]

        # Si no hubo coincidencia de número de línea pero la empresa solo opera una línea en tu sistema, asignarla directamente
        lineas_de_esta_empresa = [l for l, c in EMPRESAS_CNRT.items() if c == cod_emp]
        if len(lineas_de_esta_empresa) == 1 and not unidades_filtradas:
            unidades_filtradas = todas_unidades

        # Extraer razón social general si algún registro venía vacío
        razon_social_fallback = next((u["razonSocial"] for u in todas_unidades if u["razonSocial"]), "")

        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter=";")
            writer.writerow(headers_salida)
            
            for u in unidades_filtradas:
                raz_final = u["razonSocial"] if u["razonSocial"] else razon_social_fallback
                writer.writerow([
                    u["dominio"], u["empresaNro"], raz_final, str_linea,
                    u["interno"], u["anioModelo"], u["chasisMarca"], u["carroceriaMarca"],
                    u["vigenciaHasta"], u["vigenciaHastaInspeccionTecnica"], u["tecnicaNro"]
                ])

        print(f"✅ Línea {str_linea} (Empresa {cod_emp}): {len(unidades_filtradas)} unidades.")

if __name__ == "__main__":
    procesar()
