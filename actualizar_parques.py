import os
import re
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

# Lista de líneas a consultar
LINEAS = [
    2, 9, 10, 15, 17, 22, 24, 29, 32, 33, 37, 45, 51, 53, 56, 60, 63, 70, 74, 75, 
    79, 80, 85, 91, 92, 98, 100, 113, 119, 126, 128, 129, 133, 134, 135, 148, 154, 
    158, 159, 160, 164, 168, 177, 178, 179, 180, 195, 197
]

# Si dos o más líneas comparten empresa, mapeamos cuál usa el CSV base de cuál
# Ejemplo: la 119 y 154 usan los datos de la línea 45
REGLAS_COMPARTIDAS = {
    119: 45,
    154: 45
}

BASE_URL = "https://consultapme.cnrt.gob.ar"
OUTPUT_DIR = "parques"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def descargar_parque(linea):
    target_linea = REGLAS_COMPARTIDAS.get(linea, linea)
    
    # Si es compartida y el archivo origen ya se descargó, hacemos copia
    file_origen = os.path.join(OUTPUT_DIR, f"linea{target_linea}.csv")
    file_destino = os.path.join(OUTPUT_DIR, f"linea{linea}.csv")

    if linea in REGLAS_COMPARTIDAS and os.path.exists(file_origen):
        print(f"Línea {linea} comparte parque con Línea {target_linea}. Copiando datos...")
        with open(file_origen, 'r', encoding='utf-8') as f_in:
            content = f_in.read()
        with open(file_destino, 'w', encoding='utf-8') as f_out:
            f_out.write(content)
        return

    print(f"Buscando información para Línea {linea} en la CNRT...")
    try:
        # Petición de búsqueda a la CNRT
        search_url = f"{BASE_URL}/vehiculos_habilitados?linea={target_linea}"
        req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            
        # Buscar enlace de exportación CSV
        soup = BeautifulSoup(html, 'html.parser')
        csv_link = None
        for a in soup.find_all('a', href=True):
            if 'csv' in a['href'].lower() or 'export' in a['href'].lower():
                csv_link = a['href']
                break
                
        if not csv_link:
            # Búsqueda por regex si el enlace no es estándar
            matches = re.findall(r'href=["\'](/[^"\']*export[^"\']*csv[^"\']*)["\']', html, re.IGNORECASE)
            if matches:
                csv_link = matches[0]

        if csv_link:
            if not csv_link.startswith('http'):
                csv_link = BASE_URL + csv_link
                
            print(f"Descargando CSV para Línea {linea} desde {csv_link}...")
            csv_req = urllib.request.Request(csv_link, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(csv_req) as csv_resp:
                csv_data = csv_resp.read().decode('utf-8')
                
            with open(file_destino, 'w', encoding='utf-8') as f:
                f.write(csv_data)
            print(f"✅ Línea {linea} actualizada correctamente.")
        else:
            print(f"⚠️ No se encontró botón de descarga CSV directo para Línea {linea}.")
            
    except Exception as e:
        print(f"❌ Error al procesar Línea {linea}: {e}")

if __name__ == "__main__":
    for l in LINEAS:
        descargar_parque(l)
      
