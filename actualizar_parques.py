import pandas as pd
import requests
import os
import glob
import re

# Carpetas de destino
os.makedirs("parques", exist_ok=True)
os.makedirs("controlados", exist_ok=True)

# URL del dataset oficial de parque móvil (CNRT / JS)
URL_PARQUE_MOVIL = "https://datos.transporte.gob.ar/dataset/parque-movil-del-transporte-automotor-de-pasajeros-de-jurisdiccion-nacional"

print("Iniciando actualización de parque móvil y controlados...")

# 1. Mapeo de prefijos de internos o reglas por línea cuando comparten Razón Social/Empresa
# Si querés refinar reglas para otras empresas que comparten Razón Social, se agregan acá.
REGLAS_INTERNOS = {
    "9":  lambda x: str(x).startswith("90") or str(x).startswith("9"),   # Internos 9xx / 90xx
    "84": lambda x: str(x).startswith("84") or str(x).startswith("8"),  # Internos 8xx / 84xx
    "164": lambda x: str(x).startswith("164") or str(x).startswith("16"), # Internos 16xx / 164xx
}

def filtrar_por_linea(df, num_linea):
    """
    Filtra el DataFrame para dejar únicamente los colectivos de la línea especificada.
    """
    if df is None or df.empty:
        return df

    linea_str = str(num_linea).strip()
    
    # 1. Si el CSV tiene columna explícita 'linea' o 'lineaNro'
    col_linea = None
    for c in df.columns:
        if c.lower().replace("_", "").replace(" ", "") in ['linea', 'lineanro', 'nrolinea', 'linea_nro']:
            col_linea = c
            break

    if col_linea:
        df_filtered = df[df[col_linea].astype(str).str.strip() == linea_str]
        if not df_filtered.empty:
            return df_filtered

    # 2. Filtrado por rango o patrón de 'interno' (ej: Línea 9 -> Internos 9000s)
    col_interno = None
    for c in df.columns:
        if c.lower().replace("_", "").replace(" ", "") in ['interno', 'nrointerno', 'numinterno', 'carroceria_interno']:
            col_interno = c
            break

    if col_interno and linea_str in REGLAS_INTERNOS:
        filtro_fn = REGLAS_INTERNOS[linea_str]
        df_filtered = df[df[col_interno].apply(filtro_fn)]
        if not df_filtered.empty:
            return df_filtered

    # 3. Fallback: buscar coincidencia explícita dentro del texto de la línea
    return df

def procesar_csvs():
    # Obtener archivos descargados más recientes
    archivos_parque = glob.glob("parques/*.csv") + glob.glob("*.csv")
    
    for archivo in archivos_parque:
        # Extraer el número de línea del nombre del archivo (ej: linea9.csv -> 9)
        match = re.search(r'linea_?(\d+)', os.path.basename(archivo), re.IGNORECASE)
        if not match:
            continue
            
        num_linea = match.group(1)
        
        try:
            # Leer CSV
            df = pd.read_csv(archivo, encoding='utf-8-sig', dtype=str)
            
            # Filtrar para dejar solo las unidades pertenecientes a esta línea específica
            df_linea = filtrar_por_linea(df, num_linea)
            
            # Guardar el CSV filtrado en la carpeta parques/
            path_destino = f"parques/linea{num_linea}.csv"
            df_linea.to_csv(path_destino, index=False, encoding='utf-8-sig')
            print(f"Línea {num_linea}: {len(df_linea)} unidades procesadas correctamente.")
            
            # Procesar el archivo de controlados correspondiente si existe
            path_controlados = f"controlados/linea{num_linea}.csv"
            if os.path.exists(path_controlados):
                df_ctrl = pd.read_csv(path_controlados, encoding='utf-8-sig', dtype=str)
                df_ctrl_filtrado = filtrar_por_linea(df_ctrl, num_linea)
                df_ctrl_filtrado.to_csv(path_controlados, index=False, encoding='utf-8-sig')
                
        except Exception as e:
            print(f"Error al procesar línea {num_linea}: {e}")

if __name__ == "__main__":
    procesar_csvs()
    print("Proceso finalizado con éxito.")
