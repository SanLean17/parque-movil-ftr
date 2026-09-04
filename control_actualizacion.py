# ============================================================
# CONTROL DE ACTUALIZACIÓN CNRT
# ============================================================

from pathlib import Path
from datetime import datetime, timezone


ARCHIVO_FECHA = Path("ultima_actualizacion.txt")


# ============================================================
# COMPROBAR SI HAY QUE ACTUALIZAR
# ============================================================

def debe_actualizar():

    ahora = datetime.now(timezone.utc)

    # --------------------------------------------------------
    # SI NUNCA SE ACTUALIZÓ
    # --------------------------------------------------------

    if not ARCHIVO_FECHA.exists():

        print("No existe fecha anterior.")
        print("Se realizará la primera actualización.")

        return True

    # --------------------------------------------------------
    # LEER FECHA
    # --------------------------------------------------------

    texto = ARCHIVO_FECHA.read_text(
        encoding="utf-8"
    ).strip()

    try:

        ultima = datetime.fromisoformat(texto)

        # Compatibilidad por si existiera una fecha antigua
        # sin información de zona horaria.
        if ultima.tzinfo is None:
            ultima = ultima.replace(
                tzinfo=timezone.utc
            )

    except Exception:

        print("La fecha anterior no es válida.")
        print("Se realizará una actualización.")

        return True

    # --------------------------------------------------------
    # CALCULAR DIFERENCIA
    # --------------------------------------------------------

    diferencia = ahora - ultima

    dias = diferencia.total_seconds() / 86400

    print(
        f"Días desde última actualización: {dias:.2f}"
    )

    # --------------------------------------------------------
    # 15 DÍAS
    # --------------------------------------------------------

    if dias >= 15:

        print("Han pasado 15 días o más.")
        print("Corresponde actualizar CNRT.")

        return True

    print("Todavía no han pasado 15 días.")
    print("No corresponde actualizar CNRT.")

    return False


# ============================================================
# GUARDAR FECHA
# ============================================================

def guardar_fecha():

    ahora = datetime.now(timezone.utc)

    ARCHIVO_FECHA.write_text(
        ahora.isoformat(),
        encoding="utf-8"
    )

    print(
        "Fecha de actualización guardada: "
        f"{ahora.isoformat()}"
    )


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    if debe_actualizar():

        print("ACTUALIZAR")

    else:

        print("ESPERAR")
