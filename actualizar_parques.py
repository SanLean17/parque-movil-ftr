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
    "DOMINIO", "INTERNO", "MODELO (AÑO)", "HABILITADO HASTA", 
    "TÉCNICA VIGENTE HASTA", "N° TÉCNICA", "EMPRESA NRO", "RAZON SOCIAL", "LINEA"
]

def extraer_fechas_y_tecnica(cols):
    fechas = []
    vta_num = "-"
    
    # Expresión regular para detectar fechas tipo DD/MM/AAAA
    patron_fecha = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')
    
    for idx, c in enumerate(cols):
        encontrados = patron_fecha.findall(c)
        if encontrados:
            fechas.extend(encontrados)
        # Si no es fecha pero es un número/código largo pasados los datos principales
        elif idx >= 8 and c.strip() and not c.strip().startswith("20"):
            vta_num = c.strip()

    hab = fechas[0] if len(fechas) > 0 else "-"
    vta_vig = fechas[1] if len(fechas) > 1 else "-"
    
    # Si no capturamos número de oblea por posición, tomamos la última columna poblada
    if vta_num == "-" and len(cols) > 9:
        ultimo_valor = cols[-1].strip()
        if ultimo_valor and not patron_fecha.search(ultimo_valor):
            vta_num = ultimo_valor

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
                dom = cols[0] if len(cols) > 0 else "-"
                inte = cols[1] if len(cols) > 1 else "-"
                mod = cols[3] if len(cols) > 3 else "-"
                emp = str(nro_empresa)
                raz = cols[7] if len(cols) > 7 else ""

                hab, vta_vig, vta_num = extraer_fechas_y_tecnica(cols)

                filas_datos.append({
                    "dominio": dom,
                    "interno": inte,
                    "modelo": mod,
                    "habilitado_hasta": hab,
                    "vta_vigencia": vta_vig,
                    "vta_numero": vta_num,
                    "empresaNro": emp,
                    "razonSocial": raz
                })
        return filas_datos
    except Exception as e:
        print(f"  ⚠️ Error en empresa {nro_empresa}: {e}")
        return []

def procesar():
    print("🚀 Iniciando navegador para consultar CNRT...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for num_linea, cod_emp in EMPRESAS_CNRT.items():
            str_linea = str(num_linea)
            file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
            
            unidades = obtener_datos_empresa(page, cod_emp)

            with open(file_dest, "w", newline="", encoding="utf-8") as out:
                writer = csv.writer(out, delimiter=";")
                writer.writerow(headers_salida)
                
                for u in unidades:
                    writer.writerow([
                        u["dominio"], u["interno"], u["modelo"], u["habilitado_hasta"],
                        u["vta_vigencia"], u["vta_numero"], u["empresaNro"], u["razonSocial"], str_linea
                    ])

            print(f"✅ Línea {str_linea} (Empresa {cod_emp}): {len(unidades)} unidades.")

        browser.close()

if __name__ == "__main__":
    procesar()
