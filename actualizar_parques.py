import pandas as pd
import glob
import os
import re

os.makedirs("parques", exist_ok=True)
os.makedirs("controlados", exist_ok=True)

def leer_csv_robusto(path):
    """
    Lee el CSV detectando si el separador es ';' (estándar CNRT) o ','.
    """
    try:
        df = pd.read_csv(path, encoding='utf-8-sig', dtype=str, sep=';')
        if len(df.columns) > 1:
            return df
    except Exception:
        pass
        
    try:
        df = pd.read_csv(path, encoding='utf-8-sig', dtype=str, sep=',')
        return df
    except Exception as e:
        print(f"Error al leer {path}: {e}")
        return None

def obtener_columna_linea(df):
    for col in df.columns:
        clean = str(col).strip().lower().replace("_", "").replace(" ", "")
        if clean in ['linea', 'lineanro', 'nrolinea', 'linea_nro']:
            return col
    return None

def filtrar_por_linea(df, num_linea):
    if df is None or df.empty:
        return df

    linea_str = str(num_linea).strip()
    col_linea = obtener_columna_linea(df)

    if col_linea:
        # Compara el número de línea exacto como cadena de texto
        mask = df[col_linea].fillna('').astype(str).str.strip() == linea_str
        df_filtrado = df[mask]
        
        if not df_filtrado.empty:
            return df_filtrado

    return df

def procesar_archivos():
    # 1. Si hay descargas nuevas de la CNRT en descargas_raw, procesarlas primero
    archivos_raw = glob.glob("descargas_raw/*.csv")
    archivos_parques = glob.glob("parques/*.csv")
    
    # Procesar la carpeta parques/
    for archivo in archivos_parques:
        nombre = os.path.basename(archivo)
        match = re.search(r'linea_?(\d+)', nombre, re.IGNORECASE)
        if not match:
            continue
            
        num_linea = match.group(1)
        
        # Preferir archivo de descargas_raw si está disponible, de lo contrario usar parques/
        origen = archivo
        if archivos_raw:
            origen = archivos_raw[0] # Usa la descarga cruda de la empresa
            
        df = leer_csv_robusto(origen)
        if df is not None and not df.empty:
            total_antes = len(df)
            df_filtrado = filtrar_por_linea(df, num_linea)
            total_despues = len(df_filtrado)
            
            # Guardar el CSV filtrado exclusivamente para esa línea usando ';'
            df_filtrado.to_csv(archivo, index=False, encoding='utf-8-sig', sep=';')
            print(f"Línea {num_linea}: de {total_antes} filas se filtraron {total_despues} unidades correspondientes.")

    # 2. Procesar la carpeta controlados/ si aplica
    archivos_controlados = glob.glob("controlados/*.csv")
    for archivo in archivos_controlados:
        nombre = os.path.basename(archivo)
        match = re.search(r'linea_?(\d+)', nombre, re.IGNORECASE)
        if not match:
            continue
            
        num_linea = match.group(1)
        df = leer_csv_robusto(archivo)
        if df is not None and not df.empty:
            df_filtrado = filtrar_por_linea(df, num_linea)
            df_filtrado.to_csv(archivo, index=False, encoding='utf-8-sig', sep=';')

if __name__ == "__main__":
    procesar_archivos()
    print("Filtrado e independización de parques finalizado exitosamente.")
