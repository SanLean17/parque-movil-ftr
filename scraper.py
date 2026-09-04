import os
import time
import requests

# Carpeta de destino
DIR_DESCARGAS = "descargas_raw"
os.makedirs(DIR_DESCARGAS, exist_ok=True)

# Lista de IDs de empresas
EMPRESAS_IDS = list(set([
    "2058", "2062", "2008", "67", "2024", "2022", "2005", "2064", "2048", "972", 
    "2067", "2068", "2079", "2054", "2013", "2075", "2037", "2080", "2015", "359", 
    "2023", "2003", "2021", "2042", "2119", "2033", "2010", "2100", "2101", "2105", 
    "2111", "9085", "2099", "2077"
]))

# Headers para simular un navegador real y evitar bloqueos
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Referer': 'https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados'
}

def descargar_directo():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # 1. Obtener cookie de sesión inicial
    try:
        session.get("https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados", timeout=15)
    except Exception as e:
        print(f"Advertencia al conectar a CNRT: {e}")

    descargas_exitosas = 0

    for idx, emp_id in enumerate(EMPRESAS_IDS, 1):
        print(f"[{idx}/{len(EMPRESAS_IDS)}] Descargando empresa ID: {emp_id}...")
        
        # Endpoints probables de exportación directa de CNRT
        urls_a_probar = [
            f"https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados/exportar_csv?empresa_id={emp_id}",
            f"https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados?vehiculos_habilitados%5Bempresa_id%5D={emp_id}&exportar=csv",
            f"https://consultapme.cnrt.gob.ar/consulta_vehiculos_habilitados/descargar?empresa={emp_id}"
        ]

        exito = False
        for url in urls_a_probar:
            try:
                res = session.get(url, timeout=20)
                if res.status_code == 200 and len(res.content) > 100:
                    path_destino = os.path.join(DIR_DESCARGAS, f"empresa_{emp_id}.csv")
                    with open(path_destino, 'wb') as f:
                        f.write(res.content)
                    print(f"   -> ¡Descargado con éxito! ({len(res.content)} bytes)")
                    descargas_exitosas += 1
                    exito = True
                    break
            except Exception:
                continue

        if not exito:
            print(f"   x No se pudo descargar directamente la empresa {emp_id}")
            
        time.sleep(1)

    print(f"\nProceso finalizado. Se descargaron {descargas_exitosas}/{len(EMPRESAS_IDS)} archivos CSV.")

if __name__ == "__main__":
    descargar_directo()
