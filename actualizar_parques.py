import os
import re
import requests

# Mapeo de líneas y códigos de la CNRT
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
URL = "https://consultapme.cnrt.gob.ar/vehiculos_habilitados"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Origin': 'https://consultapme.cnrt.gob.ar',
    'Referer': 'https://consultapme.cnrt.gob.ar/vehiculos_habilitados'
}

def descargar_parque(linea, cod_empresa):
    file_destino = os.path.join(OUTPUT_DIR, f"linea{linea}.csv")
    print(f"Descargando Línea {linea} (Código: {cod_empresa})...")
    
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        # Extraer token CSRF
        res_get = session.get(URL, timeout=15)
        token_match = re.search(r'name="vehiculos_habilitados\[_token\]"\s+value="([^"]+)"', res_get.text)
        csrf_token = token_match.group(1) if token_match else ""

        payload = {
            'vehiculos_habilitados[tipoTransporte]': 'pa',
            'vehiculos_habilitados[dominio]': '',
            'vehiculos_habilitados[empresaNro]': str(cod_empresa),
            'vehiculos_habilitados[Enviar consulta]': '',
            'vehiculos_habilitados[_token]': csrf_token
        }
        
        res_post = session.post(URL, data=payload, timeout=20)
        
        # Inyectamos el comentario arriba con el código para que sea fácil de leer después
        header_metadata = f"<!-- nro_emp: {cod_empresa} -->\n".encode('utf-8')
        contenido_final = header_metadata + res_post.content
        
        with open(file_destino, 'wb') as f:
            f.write(contenido_final)
            
        print(f"  -> Guardado linea{linea}.csv ({len(contenido_final)} bytes)")
        
    except Exception as e:
        print(f"  -> Error en Línea {linea}: {e}")

if __name__ == "__main__":
    for linea, cod in EMPRESAS_CNRT.items():
        descargar_parque(linea, cod)
        
