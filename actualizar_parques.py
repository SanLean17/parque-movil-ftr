import pandas as pd
import glob
import os
import re

os.makedirs("parques", exist_ok=True)
os.makedirs("controlados", exist_ok=True)

def obtener_regla_linea(num_linea):
    """
    Retorna una función de filtrado basada en el número de interno o línea.
    """
    linea = str(num_linea).strip()
    
    # Mapeo de reglas por internos para líneas que comparten Razón Social / Empresa
    if linea == "9":
        return lambda x: str(x).strip().startswith("9") or str(x).strip().startswith("90")
    elif linea == "84":
        return lambda x: str(x).strip().startswith("84") or str(x).strip().startswith("8")
    elif linea == "164":
        return lambda x: str(x).strip().startswith("164") or str(x).strip().startswith("16")
    elif linea == "51":
        return lambda x: str(x).strip().startswith("51") or (x.isdigit() and 500 <= int(x) < 600)
    elif linea == "79":
        return lambda x: str(x).strip().startswith("79") or (x.isdigit() and 700 <= int(x) < 800)
    elif linea == "177":
        return lambda x: str(x).strip().startswith("177")
    elif linea == "56":
        return lambda x: str(x).strip().startswith("56") or str(x).strip().startswith("5")
    
    return None

def filtrar_dataframe(df, num_linea):
    if df is None or df.empty:
        return df

    linea_str = str(num_linea).strip()
    
    # 1. Buscar columna de línea si existe
    col_linea = None
    for col in df.columns:
        c_clean = col.lower().replace("_", "").replace(" ", "")
        if c_clean in ['linea', 'lineanro', 'nrolinea', 'linea_nro']:
            col_linea = col
            break

    if col_linea:
        df_sub = df[df[col_linea].astype(str).str.strip() == linea_str]
        if not df_sub.empty:
            return df_sub

    # 2. Buscar columna de interno y aplicar regla específica
    col_interno = None
    for col in df.columns:
        c_clean = col.lower().replace("_", "").replace(" ", "")
        if c_clean in ['interno', 'nrointerno', 'numinterno', 'carroceria_interno']:
            col_interno = col
            break

    regla = obtener_regla_linea(num_linea)
    if col_interno and regla:
        # Filtrar valores no nulos y aplicar la función
        mask = df[col_interno].fillna('').astype(str).apply(regla)
        df_sub = df[mask]
        if not df_sub.empty:
            return df_sub

    return df

def procesar_archivos():
    # Buscar todos los CSVs descargados o existentes
    archivos = glob.glob("parques/*.csv") + glob.glob("*.csv")
    
    for archivo in archivos:
        nombre = os.path.basename(archivo)
        match = re.search(r'linea_?(\d+)', nombre, re.IGNORECASE)
        if not match:
            continue
            
        num_linea = match.group(1)
        
        try:
            # Procesar archivo en parques/
            if os.path.exists(archivo):
                df_parque = pd.read_csv(archivo, encoding='utf-8-sig', dtype=str)
                df_parque_filtrado = filtrar_dataframe(df_parque, num_linea)
                path_destino = f"parques/linea{num_linea}.csv"
                df_parque_filtrado.to_csv(path_destino, index=False, encoding='utf-8-sig')
                print(f"Parque Línea {num_linea}: {len(df_parque_filtrado)} unidades separadas.")

            # Procesar archivo en controlados/ si existe
            path_ctrl = f"controlados/linea{num_linea}.csv"
            if os.path.exists(path_ctrl):
                df_ctrl = pd.read_csv(path_ctrl, encoding='utf-8-sig', dtype=str)
                df_ctrl_filtrado = filtrar_dataframe(df_ctrl, num_linea)
                df_ctrl_filtrado.to_csv(path_ctrl, index=False, encoding='utf-8-sig')
                print(f"Controlados Línea {num_linea}: {len(df_ctrl_filtrado)} registros filtrados.")

        except Exception as e:
            print(f"Error procesando la línea {num_linea}: {e}")

if __name__ == "__main__":
    procesar_archivos()
    print("Filtrado y separación de parques finalizado.")
