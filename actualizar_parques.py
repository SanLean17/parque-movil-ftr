import pandas as pd
import glob
import os
import re

os.makedirs("parques", exist_ok=True)
os.makedirs("controlados", exist_ok=True)

def obtener_nombre_columna_linea(df):
    """
    Busca la columna que corresponde a la línea sin importar mayúsculas/minúsculas.
    """
    for col in df.columns:
        c_clean = str(col).strip().lower().replace("_", "").replace(" ", "")
        if c_clean in ['linea', 'lineanro', 'nrolinea', 'linea_nro']:
            return col
    return None

def filtrar_por_columna_linea(df, num_linea):
    if df is None or df.empty:
        return df

    linea_target = str(num_linea).strip()
    col_linea = obtener_nombre_columna_linea(df)

    if col_linea:
        # Normalizamos los valores a texto para comparar exactamente
        mask = df[col_linea].astype(str).str.strip() == linea_target
        df_filtrado = df[mask]
        
        # Devuelve el subconjunto si encontró coincidencias
        if not df_filtrado.empty:
            return df_filtrado

    return df

def procesar_archivos():
    archivos = glob.glob("parques/*.csv") + glob.glob("*.csv")
    
    for archivo in archivos:
        nombre = os.path.basename(archivo)
        match = re.search(r'linea_?(\d+)', nombre, re.IGNORECASE)
        if not match:
            continue
            
        num_linea = match.group(1)
        
        try:
            # 1. Filtrar Parque Móvil
            if os.path.exists(archivo):
                df_parque = pd.read_csv(archivo, encoding='utf-8-sig', dtype=str)
                total_original = len(df_parque)
                df_parque_filtrado = filtrar_por_columna_linea(df_parque, num_linea)
                
                path_destino = f"parques/linea{num_linea}.csv"
                df_parque_filtrado.to_csv(path_destino, index=False, encoding='utf-8-sig')
                print(f"Parque Línea {num_linea}: de {total_original} paso a {len(df_parque_filtrado)} unidades.")

            # 2. Filtrar Controlados
            path_ctrl = f"controlados/linea{num_linea}.csv"
            if os.path.exists(path_ctrl):
                df_ctrl = pd.read_csv(path_ctrl, encoding='utf-8-sig', dtype=str)
                df_ctrl_filtrado = filtrar_por_columna_linea(df_ctrl, num_linea)
                df_ctrl_filtrado.to_csv(path_ctrl, index=False, encoding='utf-8-sig')
                print(f"Controlados Línea {num_linea}: {len(df_ctrl_filtrado)} registros filtrados.")

        except Exception as e:
            print(f"Error procesando la línea {num_linea}: {e}")

if __name__ == "__main__":
    procesar_archivos()
    print("Filtrado por columna 'linea' finalizado con éxito.")
