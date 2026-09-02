import os
import csv

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

def obtener_campo(row, claves):
    for k in claves:
        if k in row and row[k]:
            return str(row[k]).strip()
        # Búsqueda insensible a mayúsculas/minúsculas
        for row_k in row.keys():
            if row_k and row_k.lower() == k.lower() and row[row_k]:
                return str(row[row_k]).strip()
    return ""

def procesar():
    if not os.path.exists(ORIGEN_CSV):
        print(f"❌ No existe {ORIGEN_CSV}")
        return

    vehiculos_por_linea = {str(k): [] for k in EMPRESAS_CNRT.keys()}
    
    # Intentar leer el CSV probando delimitadores habituales
    for delim in [";", ","]:
        try:
            with open(ORIGEN_CSV, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f, delimiter=delim)
                filas = list(reader)
                if filas and len(filas[0].keys()) > 1:
                    for row in filas:
                        lin = obtener_campo(row, ["linea", "Linea", "LINEA"])
                        if lin in vehiculos_por_linea:
                            vehiculos_por_linea[lin].append(row)
                    break
        except Exception:
            continue

    headers_salida = [
        "dominio", "empresaNro", "razonSocial", "linea", "interno", 
        "modelo", "chasisMarca", "carroceriaMarca", "habilitado_hasta", 
        "vta_vigencia", "vta_numero"
    ]

    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        unidades = vehiculos_por_linea.get(str_linea, [])

        razon_social = f"LÍNEA {str_linea}"
        if unidades:
            razon_social = obtener_campo(unidades[0], ["razonSocial", "RazonSocial", "empresa"]) or razon_social

        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter=";")
            writer.writerow(headers_salida)
            
            if unidades:
                for u in unidades:
                    dom = obtener_campo(u, ["dominio", "Dominio", "patente"])
                    emp = obtener_campo(u, ["empresaNro", "EmpresaNro"]) or cod_emp
                    raz = obtener_campo(u, ["razonSocial", "RazonSocial"]) or razon_social
                    inte = obtener_campo(u, ["interno", "Interno"])
                    mod = obtener_campo(u, ["modelo", "Modelo", "anio", "Anio", "anioModelo"])
                    cha = obtener_campo(u, ["chasisMarca", "ChasisMarca", "chasis"])
                    car = obtener_campo(u, ["carroceriaMarca", "CarroceriaMarca", "carroceria"])
                    hab = obtener_campo(u, ["habilitado_hasta", "habilitadoHasta", "fechaHabilitacion", "vencimiento"])
                    vta_vig = obtener_campo(u, ["vta_vigencia", "vtaVigencia", "tecnicaVigencia", "vtavencimiento"])
                    vta_num = obtener_campo(u, ["vta_numero", "vtaNumero", "tecnicaNumero", "vtanumero"])

                    writer.writerow([dom, emp, raz, str_linea, inte, mod, cha, car, hab, vta_vig, vta_num])

        print(f"✅ Línea {str_linea}: {len(unidades)} unidades ({razon_social})")

if __name__ == "__main__":
    procesar()
