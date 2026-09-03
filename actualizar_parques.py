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

# Las columnas exactas mapeadas con tu JavaScript del frontend
headers_salida = [
    "dominio", "empresaNro", "razonSocial", "linea", "interno", 
    "anioModelo", "chasisMarca", "carroceriaMarca", "vigenciaHasta", 
    "vigenciaHastaInspeccionTecnica", "tecnicaNro"
]

def limpiar_fecha(texto):
    """ Extrae solo la fecha DD/MM/AAAA eliminando prefijos como UC: """
    match = re.search(r'\d{2}/\d{2}/\d{4}', texto)
    return match.group(0) if match else texto.strip()

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

        # Extraer nombres de encabezados reales de la CNRT para ubicar dinámicamente las columnas
        headers_cnrt = [th.text.strip().lower() for th in tabla.find_all("th")]
        
        def index_col(posibles_nombres, default_idx):
            for nombre in posibles_nombres:
                for idx, h in enumerate(headers_cnrt):
                    if nombre in h:
                        return idx
            return default_idx

        # Índices según tus capturas del CSV oficial
        idx_dom = index_col(["dominio"], 0)
        idx_inte = index_col(["interno"], 1)
        idx_mod = index_col(["aniomodelo"], 3)
        idx_emp = index_col(["empresanro"], 5)
        idx_razon = index_col(["razonsocial"], 7)
        idx_vta_vig = index_col(["vigenciahastainspec", "vigenciahastaic"], 8)
        idx_vta_num = index_col(["tecnicanro"], 9)
        idx_linea = index_col(["linea"], 19)
        idx_hab = index_col(["vigenciahasta"], len(headers_cnrt) - 1)

        filas_datos = []
        for tr in tabla.find_all("tr")[1:]:
            cols = [td.text.strip() for td in tr.find_all("td")]
            if len(cols) > max(idx_dom, idx_inte):
                
                dom = cols[idx_dom] if idx_dom < len(cols) else ""
                inte = cols[idx_inte] if idx_inte < len(cols) else ""
                mod = cols[idx_mod] if idx_mod < len(cols) else ""
                emp = cols[idx_emp] if idx_emp < len(cols) else str(nro_empresa)
                raz = cols[idx_razon] if idx_razon < len(cols) else ""
                vta_vig = limpiar_fecha(cols[idx_vta_vig]) if idx_vta_vig < len(cols) else ""
                vta_num = cols[idx_vta_num] if idx_vta_num < len(cols) else ""
                linea_val = cols[idx_linea] if idx_linea < len(cols) else ""
                hab = limpiar_fecha(cols[idx_hab]) if idx_hab < len(cols) else ""

                # Limpieza del número de línea para compararlo numéricamente
                match_lin = re.search(r'\d+', linea_val)
                str_linea_num = match_lin.group(0) if match_lin else ""

                filas_datos.append({
                    "dominio": dom,
                    "empresaNro": emp if emp else str(nro_empresa),
                    "razonSocial": raz,
                    "linea_num": str_linea_num,
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
    
    unidades_por_empresa = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        codigos_unicos = set(EMPRESAS_CNRT.values())

        for cod_emp in codigos_unicos:
            print(f"📡 Consultando empresa CNRT N° {cod_emp}...")
            unidades_por_empresa[cod_emp] = obtener_datos_empresa(page, cod_emp)

        browser.close()

    print("\n📂 Filtrando y generando archivos CSV por línea...")
    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        
        todas_unidades = unidades_por_empresa.get(cod_emp, [])
        lineas_de_esta_empresa = [l for l, c in EMPRESAS_CNRT.items() if c == cod_emp]

        # 1. Filtrado por la columna 'linea' (Columna T)
        unidades_filtradas = [
            u for u in todas_unidades 
            if u["linea_num"] == str_linea or u["linea_num"] == str_linea.zfill(3) or u["linea_num"] == str_linea.zfill(4)
        ]

        # 2. Si la empresa solo maneja 1 línea registrada en tu lista, asigna directo si no hubo match
        if not unidades_filtradas and len(lineas_de_esta_empresa) == 1:
            unidades_filtradas = todas_unidades

        # Rescate de Razón Social si alguna venía en blanco
        razon_fallback = next((u["razonSocial"] for u in todas_unidades if u["razonSocial"]), "")

        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter=";")
            writer.writerow(headers_salida)
            
            for u in unidades_filtradas:
                raz_final = u["razonSocial"] if u["razonSocial"] else razon_fallback
                writer.writerow([
                    u["dominio"],
                    u["empresaNro"],
                    raz_final,
                    str_linea,
                    u["interno"],
                    u["anioModelo"],
                    u["chasisMarca"],
                    u["carroceriaMarca"],
                    u["vigenciaHasta"],
                    u["vigenciaHastaInspeccionTecnica"],
                    u["tecnicaNro"]
                ])

        print(f"✅ Línea {str_linea} (Empresa {cod_emp}): {len(unidades_filtradas)} unidades (de {len(todas_unidades)} de la Razón Social).")

if __name__ == "__main__":
    procesar()
