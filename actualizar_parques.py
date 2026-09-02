import os
import requests

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
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://consultapme.cnrt.gob.ar"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Origin': BASE_URL,
    'Referer': f"{BASE_URL}/vehiculos_habilitados"
}

def descargar_parque(linea, cod_empresa):
    file_destino = os.path.join(OUTPUT_DIR, f"linea{linea}.csv")
    print(f"\n--- Procesando Línea {linea} (Habilitación: {cod_empresa}) ---")
    
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        # 1. Crear sesión visitando la portada
        session.get(f"{BASE_URL}/vehiculos_habilitados", timeout=20)
        
        # 2. Hacer la consulta del formulario vía POST
        payload = {
            'tipo_transporte': '1',
            'dominio': '',
            'empresa': str(cod_empresa)
        }
        
        res_post = session.post(f"{BASE_URL}/vehiculos_habilitados", data=payload, timeout=20)
        
        # 3. Intentar obtener el archivo exportado tras la consulta exitosa
        url_csv = f"{BASE_URL}/vehiculos_habilitados/exportar_csv"
        res_csv = session.get(url_csv, timeout=20)
        
        # Validar si devolvió un archivo CSV real
        if res_csv.status_code == 200 and len(res_csv.content) > 100 and b"<html" not in res_csv.content.lower():
            with open(file_destino, 'wb') as f:
                f.write(res_csv.content)
            print(f"✅ ÉXITO: linea{linea}.csv guardado ({len(res_csv.content)} bytes)")
        else:
            # Fallback: Extraer la tabla del POST directo si no genera el CSV
            if res_post.status_code == 200 and len(res_post.content) > 2000:
                with open(file_destino, 'wb') as f:
                    f.write(res_post.content)
                print(f"✅ ÉXITO (HTML Tabla): linea{linea}.csv guardado ({len(res_post.content)} bytes)")
            else:
                print(f"⚠️ No se obtuvieron datos. Status CSV: {res_csv.status_code}")
            
    except Exception as e:
        print(f"❌ Error en Línea {linea}: {e}")

if __name__ == "__main__":
    for linea, cod in EMPRESAS_CNRT.items():
        descargar_parque(linea, cod)
