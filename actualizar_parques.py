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

def procesar():
    if not os.path.exists(ORIGEN_CSV):
        print(f"❌ No existe {ORIGEN_CSV}")
        return

    vehiculos_por_linea = {str(k): [] for k in EMPRESAS_CNRT.keys()}
    
    with open(ORIGEN_CSV, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            lin = str(row.get("linea") or row.get("Linea") or "").strip()
            if lin in vehiculos_por_linea:
                vehiculos_por_linea[lin].append(row)

    for num_linea, cod_emp in EMPRESAS_CNRT.items():
        str_linea = str(num_linea)
        file_dest = os.path.join(OUTPUT_DIR, f"linea{str_linea}.csv")
        unidades = vehiculos_por_linea.get(str_linea, [])

        razon_social = f"LÍNEA {str_linea}"
        if unidades:
            razon_social = unidades[0].get("razonSocial") or unidades[0].get("RazonSocial") or razon_social

        with open(file_dest, "w", newline="", encoding="utf-8") as out:
            # FORZAMOS DELIMITADOR PUNTO Y COMA
            writer = csv.writer(out, delimiter=";")
            writer.writerow(["dominio", "empresaNro", "razonSocial", "linea", "interno", "chasisMarca", "carroceriaMarca"])
            
            if unidades:
                for u in unidades:
                    dom = u.get("dominio") or u.get("Dominio") or ""
                    emp = u.get("empresaNro") or u.get("EmpresaNro") or cod_emp
                    raz = u.get("razonSocial") or u.get("RazonSocial") or razon_social
                    inte = u.get("interno") or u.get("Interno") or ""
                    cha = u.get("chasisMarca") or u.get("ChasisMarca") or ""
                    car = u.get("carroceriaMarca") or u.get("CarroceriaMarca") or ""
                    writer.writerow([dom, emp, raz, str_linea, inte, cha, car])

        print(f"✅ Línea {str_linea}: {len(unidades)} unidades ({razon_social})")

if __name__ == "__main__":
    procesar()
