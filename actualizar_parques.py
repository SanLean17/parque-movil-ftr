import os
import csv
import requests
from bs4 import BeautifulSoup

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
    "modelo", "chasisMarca", "carroceriaMarca", "habilitado_hasta", 
    "vta_vigencia", "vta_numero"
]

def obtener_datos_empresa(session, nro_empresa):
    payload = {
        "tipo_transporte": "Pasajeros",
        "dominio": "",
        "nro_habilitacion": str(nro_empresa)
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": URL_FORM
    }
    
    try:
        response = session.post(URL_FORM, data=payload, headers=headers, timeout=20)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        tabla = soup.find("table")
        if not tabla:
            return []

        filas_datos = []
        for tr in tabla.find_all("tr")[1:]:
            cols = [td.text.strip() for td in tr.find_all("td")]
            if len(cols) >= 10:
                # Mapeo según la estructura que muestra la web de CNRT:
                # [0] Dominio, [1] Int, [2] Servicios, [3] Modelo, [4] Asientos, 
                # [5] N° Emp, [6] CUIT, [7] Razon Social, [8] Habilitado Hasta, [9] Tecnica Vigente Hasta, [10] Tecnica Nro
                dom = cols[0]
                inte = cols[1]
                mod = cols[3]
                emp = cols[5]
                raz = cols[7]
                hab = cols[8]
                vta_vig = cols[9]
                vta_num = cols[10] if len(cols) > 10 else ""

                filas_datos.append({
                    "dominio": dom,
                    "empresaNro": emp,
                    "razonSocial": raz,
                    "interno": inte,
                    "modelo": mod,
                    "chasisMarca": "",
                    "carroceriaMarca": "",
                    "habilitado_hasta": hab,
                    "vta_vigencia": vta_vig,
                    "vta_numero": vta_num
                })
        return filas_datos
    except Exception as e:
        print(f"  ⚠️ Error consultando empresa {nro_empresa}: {e}")
        return []

def procesar():
    session = requests.Session()
    print("🚀 Consultando datos directamente en la web de CNRT...")

    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        
        unidades = obtener_datos_empresa(session, cod_emp)
        razon_social = unidades[0]["razonSocial"] if unidades else f"LÍNEA {str_linea}"

        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter=";")
            writer.writerow(headers_salida)
            
            for u in unidades:
                writer.writerow([
                    u["dominio"], u["empresaNro"], u["razonSocial"], str_linea,
                    u["interno"], u["modelo"], u["chasisMarca"], u["carroceriaMarca"],
                    u["habilitado_hasta"], u["vta_vigencia"], u["vta_numero"]
                ])

        print(f"✅ Línea {str_linea} (Empresa {cod_emp}): {len(unidades)} unidades procesadas.")

if __name__ == "__main__":
    procesar()
