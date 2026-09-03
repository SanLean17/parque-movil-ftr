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

# Nombres exactos de columnas requeridos por la web
headers_salida = [
    "dominio", "empresaNro", "razonSocial", "linea", "interno", 
    "anioModelo", "chasisMarca", "carroceriaMarca", "vigenciaHasta", 
    "vigenciaHastaInspeccionTecnica", "tecnicaNro"
]

def formatear_fecha(texto):
    """ Deja la fecha limpia en formato DD/MM/AAAA """
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

        # Leer encabezados reales de la tabla de la CNRT
        headers_tabla = [th.text.strip() for th in tabla.find_all("th")]
        
        def get_idx(nombre_col):
            try:
                return headers_tabla.index(nombre_col)
            except ValueError:
                return -1

        idx_dom = get_idx("dominio")
        idx_emp = get_idx("empresaNro")
        idx_razon = get_idx("razonSocial")
        idx_linea = get_idx("linea")
        idx_inte = get_idx("interno")
        idx_mod = get_idx("anioModelo")
        idx_hab = get_idx("vigenciaHasta")
        
        # Buscar inspección técnica (probando ambos nombres de columna)
        idx_vta_vig = get_idx("vigenciaHastaInspec")
        if idx_vta_vig == -1:
            idx_vta_vig = get_idx("vigenciaHastaInspeccionTecnica")
            
        idx_vta_num = get_idx("tecnicaNro")

        filas_datos = []
        for tr in tabla.find_all("tr")[1:]:
            cols = [td.text.strip() for td in tr.find_all("td")]
            if len(cols) > 0:
                dom = cols[idx_dom] if idx_dom != -1 and idx_dom < len(cols) else ""
                emp = cols[idx_emp] if idx_emp != -1 and idx_emp < len(cols) else str(nro_empresa)
                raz = cols[idx_razon] if idx_razon != -1 and idx_razon < len(cols) else ""
                lin_raw = cols[idx_linea] if idx_linea != -1 and idx_linea < len(cols) else ""
                inte = cols[idx_inte] if idx_inte != -1 and idx_inte < len(cols) else ""
                mod = cols[idx_mod] if idx_mod != -1 and idx_mod < len(cols) else ""
                hab = formatear_fecha(cols[idx_hab]) if idx_hab != -1 and idx_hab < len(cols) else ""
                vta_vig = formatear_fecha(cols[idx_vta_vig]) if idx_vta_vig != -1 and idx_vta_vig < len(cols) else ""
                vta_num = cols[idx_vta_num] if idx_vta_num != -1 and idx_vta_num < len(cols) else ""

                # Extraer número limpio de la línea (ej: "9", "164")
                match_lin = re.search(r'\d+', lin_raw)
                str_linea_num = str(int(match_lin.group(0))) if match_lin else ""

                filas_datos.append({
                    "dominio": dom,
                    "empresaNro": emp,
                    "razonSocial": raz,
                    "linea_num": str_linea_num,
                    "interno": inte,
                    "anioModelo": mod,
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

    print("\n📂 Filtrando unidades estrictamente por número de línea...")
    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        
        todas_unidades = unidades_por_empresa.get(cod_emp, [])
        
        # Filtro estricto: la unidad debe coincidir exactamente con la línea buscada
        unidades_filtradas = [
            u for u in todas_unidades 
            if u["linea_num"] == str_linea
        ]

        # Si la empresa solo tiene 1 línea asignada en tu dict y la columna línea venía vacía
        lineas_de_esta_empresa = [l for l, c in EMPRESAS_CNRT.items() if c == cod_emp]
        if not unidades_filtradas and len(lineas_de_esta_empresa) == 1:
            unidades_filtradas = todas_unidades

        # Razón social de respaldo
        razon_fallback = next((u["razonSocial"] for u in todas_unidades if u["razonSocial"]), "")

        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter=";")
            writer.writerow(headers_salida)
            
            for u in unidades_filtradas:
                raz = u["razonSocial"] if u["razonSocial"] else razon_fallback
                writer.writerow([
                    u["dominio"],
                    u["empresaNro"],
                    raz,
                    str_linea,
                    u["interno"],
                    u["anioModelo"],
                    "", # chasisMarca
                    "", # carroceriaMarca
                    u["vigenciaHasta"],
                    u["vigenciaHastaInspeccionTecnica"],
                    u["tecnicaNro"]
                ])

        print(f"✅ Línea {str_linea} (Empresa {cod_emp}): {len(unidades_filtradas)} unidades agregadas al CSV.")

if __name__ == "__main__":
    procesar()
