import os
import requests

EMPRESAS_CNRT = {
    2: "2058",
    9: "2062",
    10: "2008",
    15: "67",
    17: "2024",
    22: "2022",
    24: "2005",
    29: "2064",
    32: "2048",
    33: "972",
    37: "2067",
    45: "2068",
    51: "2079",
    53: "2054",
    56: "2013",
    60: "2075",
    63: "2037",
    70: "2080",
    74: "2079",
    79: "2079",
    80: "2015",
    85: "359",
    91: "2013",
    92: "2023",
    95: "2003",
    98: "2021",
    100: "2042",
    113: "2037",
    119: "2068",
    126: "2119",
    128: "2048",
    129: "2033",
    133: "2010",
    134: "2042",
    135: "2013",
    148: "2033",
    154: "2068",
    158: "2048",
    159: "2100",
    160: "2101",
    164: "2062",
    168: "2105",
    177: "2079",
    178: "2111",
    179: "9085",
    180: "2099",
    195: "2077",
    197: "2033"
}

OUTPUT_DIR = "parques"
os.makedirs(OUTPUT_DIR, exist_ok=True)

headers_base = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9',
}

def descargar_parque(linea, cod_empresa):
    file_destino = os.path.join(OUTPUT_DIR, f"linea{linea}.csv")
    print(f"--- Procesando Línea {linea} (Habilitación: {cod_empresa}) ---")
    
    session = requests.Session()
    session.headers.update(headers_base)
    
    try:
        # 1. Visitar la página inicial para recibir la cookie de sesión
        session.get("https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados", timeout=20)
        
        # 2. Enviar la consulta con multipart/form-data como un navegador real
        payload_data = {
            'tipo_transporte': '1',
            'dominio': '',
            'empresa': str(cod_empresa)
        }
        
        session.post(
            "https://consultapme.cnrt.gob.ar/vehiculos_habilitados", 
            data=payload_data, 
            timeout=20
        )
        
        # 3. Exportar directamente el CSV
        url_csv = f"https://consultapme.cnrt.gob.ar/vehiculos_habilitados/exportar_csv?empresa={cod_empresa}"
        res_csv = session.get(url_csv, timeout=20)
        
        if res_csv.status_code == 200 and len(res_csv.content) > 100:
            with open(file_destino, 'wb') as f:
                f.write(res_csv.content)
            print(f"✅ EXITO: linea{linea}.csv guardado ({len(res_csv.content)} bytes)")
        else:
            print(f"⚠️ No se obtuvieron datos para la Línea {linea}")
            
    except Exception as e:
        print(f"❌ Error en Línea {linea}: {e}")

if __name__ == "__main__":
    for linea, cod in EMPRESAS_CNRT.items():
        descargar_parque(linea, cod)
