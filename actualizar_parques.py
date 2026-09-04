import pandas as pd
import glob
import os
import re

# Asegurar que existan las carpetas de destino
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
    """
    Busca automáticamente el nombre de la columna que contiene el número de línea.
    """
    for col in df.columns:
        clean = str(col).strip().lower().replace("_", "").replace(" ", "")
        if clean in ['linea', 'lineanro', 'nrolinea', 'linea_nro']:
            return col
    return None

def filtrar_por_linea(df, num_linea):
    """
    Filtra las filas donde el valor de la columna 'linea' coincide exactamente con num_linea.
    """
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
    # 1. Buscar las descargas crudas hechas por scraper.py
    archivos_raw = glob.glob("descargas_raw/*.csv")
    
    # 2. Buscar todos los archivos en la carpeta parques/
    archivos_parques = glob.glob("parques/*.csv")
    
    # Mapeo de líneas y sus datos acumulados de las descargas
    dfs_raw = []
    if archivos_raw:
        print(f"Cargando {len(archivos_raw)} archivos descargados de CNRT...")
        for raw_file in archivos_raw:
            df_temp = leer_csv_robusto(raw_file)
            if df_temp is not None and not df_temp.empty:
                dfs_raw.append(df_temp)
    
    # Si logramos descargar datos de la CNRT, unificamos todo
    df_global_cnrt = pd.concat(dfs_raw, ignore_index=True) if dfs_raw else None

    # Procesar cada archivo dentro de parques/
    for archivo in archivos_parques:
        nombre = os.path.basename(archivo)
        
        # Extraer el número de línea del nombre de archivo (ej: linea9.csv -> 9)
        match = re.search(r'linea_?(\d+)', nombre, re.IGNORECASE)
        if not match:
            continue
            
        num_linea = match.group(1)
        
        # Si tenemos los datos frescos descargados de la CNRT, los usamos
        if df_global_cnrt is not None and not df_global_cnrt.empty:
            df_filtrado = filtrar_por_linea(df_global_cnrt, num_linea)
            if df_filtrado is not None and not df_filtrado.empty:
                df_filtrado.to_csv(archivo, index=False, encoding='utf-8-sig', sep=';')
                print(f"Línea {num_linea}: Actualizado desde CNRT con {len(df_filtrado)} unidades.")
                continue

        # Si no hubo descargas de la CNRT, limpia el archivo existente por seguridad
        df_local = leer_csv_robusto(archivo)
        if df_local is not None and not df_local.empty:
            df_filtrado = filtrar_por_linea(df_local, num_linea)
            df_filtrado.to_csv(archivo, index=False, encoding='utf-8-sig', sep=';')
            print(f"Línea {num_linea}: Filtrado local con {len(df_filtrado)} unidades.")

    # 3. Procesar carpeta controlados/ si existe
    archivos_controlados = glob.glob("controlados/*.csv")
    for archivo in archivos_controlados:
        nombre = os.path.basename(archivo)
        match = re.search(r'linea_?(\d+)', nombre, re.IGNORECASE)
        if not match:
            continue
            
        num_linea = match.group(1)
        df_local = leer_csv_robusto(archivo)
        if df_local is not None and not df_local.empty:
            df_filtrado = filtrar_por_linea(df_local, num_linea)
            df_filtrado.to_csv(archivo, index=False, encoding='utf-8-sig', sep=';')

if __name__ == "__main__":
    procesar_archivos()
    print("Procesamiento y separación de líneas completado exitosamente.")
