import os
import requests
import re
from bs4 import BeautifulSoup

# Lista de líneas a procesar
LINEAS = [
    2, 9, 10, 15, 17, 22, 24, 29, 32, 33, 37, 45, 51, 53, 56, 60, 63, 70, 74, 75, 
    79, 80, 85, 91, 92, 98, 100, 113, 119, 126, 128, 129, 133, 134, 135, 148, 154, 
    158, 159, 160, 164, 168, 177, 178, 179, 180, 195, 197
]

# Si conocés empresas que comparten archivo, las mapeás acá
# Ejemplo: la 119 y 154 usan la misma consulta que la 45
REGLAS_COMPARTIDAS = {
    119: 45,
    154: 45
}

BASE_URL = "https://consultapme.cnrt.gob.ar"
OUTPUT_DIR = "parques"
os.makedirs(OUTPUT_DIR, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

session = requests.Session()

def descargar_parque(linea):
    linea_consulta = REGLAS_COMPARTIDAS.get(linea, linea)
    file_destino = os.path.join(OUTPUT_DIR, f"linea{linea}.csv")
    
    print(f"--- Procesando Línea {linea} (Consulta CNRT: Línea {linea_consulta}) ---")
    
    try:
        # 1. Consultar la página de búsqueda para obtener el ID de empresa dinámicamente
        url_busqueda = f"{BASE_URL}/vehiculos_habilitados?linea={linea_consulta}"
        res = session.get(url_busqueda, headers=headers, timeout=20)
        
        id_empresa = None
        # Buscar el ID de empresa en el HTML
        matches = re.findall(r'empresa=(\d+)', res.text)
        if matches:
            id_empresa = matches[0]
            
        if id_empresa:
            # 2. Descargar directamente el archivo VehiculosPasajeros.csv oficial
            url_csv = f"{BASE_URL}/vehiculos_habilitados/exportar_csv?empresa={id_empresa}"
            res_csv = session.get(url_csv, headers=headers, timeout=20)
            
            if res_csv.status_code == 200 and len(res_csv.text) > 50:
                with open(file_destino, 'w', encoding='utf-8') as f:
                    f.write(res_csv.text)
                print(f"✅ ÉXITO: linea{linea}.csv actualizado ({len(res_csv.text)} bytes).")
            else:
                print(f"⚠️ El servidor de la CNRT no devolvió datos válidos para Línea {linea}.")
        else:
            # Si no requirió ID o tiene descarga directa por línea
            url_directa = f"{BASE_URL}/vehiculos_habilitados/exportar_csv?linea={linea_consulta}"
            res_directa = session.get(url_directa, headers=headers, timeout=20)
            if res_directa.status_code == 200 and len(res_directa.text) > 50:
                with open(file_destino, 'w', encoding='utf-8') as f:
                    f.write(res_directa.text)
                print(f"✅ ÉXITO: linea{linea}.csv actualizado vía directa.")
            else:
                print(f"❌ No se pudo detectar el ID de empresa para Línea {linea}.")

    except Exception as e:
        print(f"❌ Error procesando Línea {linea}: {e}")

if __name__ == "__main__":
    for l in LINEAS:
        descargar_parque(l)
