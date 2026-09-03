import pandas as pd
import glob
import os
import re

os.makedirs("parques", exist_ok=True)
os.makedirs("controlados", exist_ok=True)

def leer_csv_robusto(path):
    """
    Intenta leer el CSV detectando si usa comas o punto y coma como separador.
    """
    try:
        # Primero probamos con punto y coma (;) que es el estándar de CNRT
        df = pd.read_csv(path, encoding='utf-8-sig', dtype=str, sep=';')
        if len(df.columns) > 1:
            return df
    except Exception:
        pass
        
    try:
        # Fallback a coma (,)
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
        # Compara el valor de la columna 'linea' ignorando espacios o ceros extra
        mask = df[col_linea].fillna('').astype(str).str.strip() == linea_str
        df_filtrado = df[mask]
        
        if not df_filtrado.empty:
            return df_filtrado

    return df

def procesar_archivos():
    # Procesar la carpeta parques
    archivos_parques = glob.glob("parques/*.csv")
    
    for archivo in archivos_parques:
        nombre = os.path.basename(archivo)
        match = re.search(r'linea_?(\d+)', nombre, re.IGNORECASE)
        if not match:
            continue
            
        num_linea = match.group(1)
        
        df = leer_csv_robusto(archivo)
        if df is not None and not df.empty:
            total_antes = len(df)
            df_filtrado = filtrar_por_linea(df, num_linea)
            total_despues = len(df_filtrado)
            
            # Guardamos manteniendo el separador ';' original de los CSVs
            df_filtrado.to_csv(archivo, index=False, encoding='utf-8-sig', sep=';')
            print(f"Línea {num_linea}: de {total_antes} filas paso a {total_despues} unidades reales.")

    # Procesar la carpeta controlados si existen archivos
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
    print("Filtrado y separación por punto y coma finalizado.")
