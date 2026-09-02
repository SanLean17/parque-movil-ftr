import os
import csv

# Mapeo de Líneas y su Código de Empresa (N° EMP) en CNRT
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
ORIGEN_CSV = "VehiculosPasajeros.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def procesar_parques_locales():
    if not os.path.exists(ORIGEN_CSV):
        print(f"❌ Error: No se encuentra el archivo base '{ORIGEN_CSV}'.")
        return

    # Estructura para agrupar vehículos por número de línea
    vehiculos_por_linea = {str(num): [] for num in EMPRESAS_CNRT.keys()}

    print(f"Leyendo datos desde '{ORIGEN_CSV}'...")
    
    with open(ORIGEN_CSV, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f, delimiter=";")
        
        for row in reader:
            linea_raw = str(row.get("linea", "")).strip()
            
            # Si el registro pertenece a una de nuestras líneas
            if linea_raw in vehiculos_por_linea:
                vehiculos_por_linea[linea_raw].append({
                    "dominio": row.get("dominio", "").strip(),
                    "empresaNro": row.get("empresaNro", "").strip(),
                    "razonSocial": row.get("razonSocial", "").strip(),
                    "linea": linea_raw,
                    "interno": row.get("interno", "").strip(),
                    "chasisMarca": row.get("chasisMarca", "").strip(),
                    "carroceriaMarca": row.get("CarroceriaMarca", "").strip()
                })

    # Guardar cada línea en su respectivo parque/lineaXX.csv
    for linea_num, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(linea_num)
        file_destino = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        registros = vehiculos_por_linea.get(str_linea, [])

        with open(file_destino, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            # Encabezado esperado por index.html y PapaParse
            writer.writerow(["dominio", "empresaNro", "razonSocial", "linea", "interno", "chasisMarca", "carroceriaMarca"])

            if registros:
                for reg in registros:
                    writer.writerow([
                        reg["dominio"],
                        reg["empresaNro"] or cod_emp,
                        reg["razonSocial"],
                        reg["linea"],
                        reg["interno"],
                        reg["chasisMarca"],
                        reg["carroceriaMarca"]
                    ])
                print(f"  -> Línea {str_linea}: {len(registros)} colectivos guardados ({registros[0]['razonSocial']})")
            else:
                # Si la línea no tiene registros cargados aún en el CSV base
                writer.writerow(["", cod_emp, f"LÍNEA {str_linea}", str_linea, "", "", ""])
                print(f"  -> Línea {str_linea}: Sin registros en el CSV base.")

if __name__ == "__main__":
    procesar_parques_locales()
