import os
import re
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
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://consultapme.cnrt.gob.ar"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Origin': BASE_URL,
    'Referer': f"{BASE_URL}/vehiculos_habilitados"
}

def extraer_datos_de_html(html_str, cod_empresa):
    soup = BeautifulSoup(html_str, 'html.parser')
    
    # 1. Intentar obtener el nombre de la empresa desde el HTML
    nombre_empresa = ""
    # Buscar en selects, headers o badges de la respuesta
    option_selected = soup.find('option', selected=True)
    if option_selected and option_selected.text.strip():
        nombre_empresa = option_selected.text.strip()
    
    # 2. Buscar todas las filas de tabla <tr>
    filas = soup.find_all('tr')
    registros = []

    for tr in filas:
        tds = tr.find_all('td')
        if len(tds) >= 2:
            texto_fila = [td.get_text(strip=True) for td in tds]
            registros.append(texto_fila)

    # 3. Si no encontró <tr> explícitos, buscar por expresiones regulares (Patentes/Dominios)
    if not registros:
        # Busca patrones de patentes argentinas (ej: AA123CD o ABC123)
        patentes = re.findall(r'\b[A-Z]{2}\d{3}[A-Z]{2}\b|\b[A-Z]{3}\d{3}\b', html_str, re.IGNORECASE)
        patentes = list(dict.fromkeys([p.upper() for p in patentes])) # Remover duplicados
        
        for pat in patentes:
            registros.append([pat, "", nombre_empresa or f"EMPRESA {cod_empresa}"])

    return registros, nombre_empresa

def descargar_parque(linea, cod_empresa):
    file_destino = os.path.join(OUTPUT_DIR, f"linea{linea}.csv")
    print(f"\n--- Procesando Línea {linea} (Habilitación: {cod_empresa}) ---")
    
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        session.get(f"{BASE_URL}/vehiculos_habilitados", timeout=20)
        
        payload = {
            'tipo_transporte': '1',
            'dominio': '',
            'empresa': str(cod_empresa)
        }
        
        res_post = session.post(f"{BASE_URL}/vehiculos_habilitados", data=payload, timeout=20)
        
        if res_post.status_code == 200 and len(res_post.content) > 500:
            html_content = res_post.text
            registros, emp_nombre = extraer_datos_de_html(html_content, cod_empresa)
            
            # Guardar siempre un CSV limpio
            with open(file_destino, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['nro_emp', 'empresa', 'dominio', 'interno', 'carroceria', 'chasis', 'modelo'])
                
                if registros:
                    for reg in registros:
                        dom = reg[0] if len(reg) > 0 else ''
                        inter = reg[1] if len(reg) > 1 else ''
                        emp = reg[2] if len(reg) > 2 and reg[2] else (emp_nombre or f'EMPRESA LÍNEA {linea}')
                        carroc = reg[3] if len(reg) > 3 else ''
                        chas = reg[4] if len(reg) > 4 else ''
                        mod = reg[5] if len(reg) > 5 else ''
                        
                        writer.writerow([cod_empresa, emp, dom, inter, carroc, chas, mod])
                    print(f"✅ ÉXITO: linea{linea}.csv guardado con {len(registros)} unidades.")
                else:
                    # Guardar al menos la cabecera con la empresa para que la web no rompa
                    writer.writerow([cod_empresa, emp_nombre or f'EMPRESA LÍNEA {linea}', '', '', '', '', ''])
                    print(f"⚠️ No se extrajeron dominios, guardada estructura base para Línea {linea}")
        else:
            print(f"⚠️ Respuesta vacía o error HTTP para Línea {linea}")
            
    except Exception as e:
        print(f"❌ Error en Línea {linea}: {e}")

if __name__ == "__main__":
    for linea, cod in EMPRESAS_CNRT.items():
        descargar_parque(linea, cod)
