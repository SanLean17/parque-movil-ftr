import os
import re
import csv
import requests

# Mapeo de líneas y sus códigos de empresa en la CNRT
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

def descargar_y_convertir_a_csv(linea, cod_empresa):
    file_destino = os.path.join(OUTPUT_DIR, f"linea{linea}.csv")
    print(f"Procesando Línea {linea} (Código CNRT: {cod_empresa})...")
    
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        # 1. Obtener Token CSRF
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
        
        # 2. Hacer la petición POST a la CNRT
        res_post = session.post(URL, data=payload, timeout=20)
        html_text = res_post.text

        # 3. Extraer la Razón Social real
        match_razon = re.search(r'Empresa:\s*([^\n\r<]+)', html_text, re.IGNORECASE)
        razon_social = match_razon.group(1).strip() if match_razon else f"LÍNEA {linea}"

        # 4. Extraer todos los dominios/patentes únicas
        patentes = set(re.findall(r'\b[A-Z]{2}\d{3}[A-Z]{2}\b|\b[A-Z]{3}\d{3}\b', html_text.upper()))
        
        # 5. Generar el CSV delimitado por ";" que tu index.html Lee con PapaParse
        with open(file_destino, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=';')
            # Encabezados exactos que busca tu index.html
            writer.writerow(['dominio', 'empresaNro', 'razonSocial', 'linea'])
            
            if patentes:
                for pat in patentes:
                    writer.writerow([pat, str(cod_empresa), razon_social, str(linea)])
            else:
                # Si no hay patentes, grabamos una fila técnica con el nombre de la empresa para que al menos se vea en el listado
                writer.writerow(['', str(cod_empresa), razon_social, str(linea)])
                
        print(f"  -> Generado CSV exitoso: {len(patentes)} colectivos para {razon_social}")
        
    except Exception as e:
        print(f"  -> Error procesando Línea {linea}: {e}")

if __name__ == "__main__":
    for linea, cod in EMPRESAS_CNRT.items():
        descargar_y_convertir_a_csv(linea, cod)
