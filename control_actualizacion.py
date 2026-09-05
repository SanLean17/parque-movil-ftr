# ============================================================
# CONTROL DE ACTUALIZACIÓN CNRT
# PARQUE MÓVIL FTR
# ============================================================

from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# ARCHIVO NUEVO
# ============================================================

ARCHIVO_FECHA = Path(
    "ultima_actualizacion_parque.txt"
)


# ============================================================
# ARCHIVO ANTIGUO
#
# Se mantiene como compatibilidad para no perder
# la fecha que ya tenía el sistema.
# ============================================================

ARCHIVO_FECHA_ANTIGUO = Path(
    "ultima_actualizacion.txt"
)


# ============================================================
# OBTENER ARCHIVO DE FECHA
# ============================================================

def obtener_archivo_fecha():

    if ARCHIVO_FECHA.exists():
        return ARCHIVO_FECHA

    if ARCHIVO_FECHA_ANTIGUO.exists():
        return ARCHIVO_FECHA_ANTIGUO

    return ARCHIVO_FECHA


# ============================================================
# COMPROBAR SI HAY QUE ACTUALIZAR
# ============================================================

def debe_actualizar():

    ahora = datetime.now(timezone.utc)

    archivo_fecha = obtener_archivo_fecha()

    # --------------------------------------------------------
    # SI NUNCA SE ACTUALIZÓ
    # --------------------------------------------------------

    if not archivo_fecha.exists():

        print(
            "No existe fecha anterior."
        )

        print(
            "Se realizará la primera actualización CNRT."
        )

        return True

    # --------------------------------------------------------
    # LEER FECHA
    # --------------------------------------------------------

    texto = archivo_fecha.read_text(
        encoding="utf-8"
    ).strip()

    try:

        ultima = datetime.fromisoformat(
            texto
        )

        # Compatibilidad con fechas antiguas
        # sin zona horaria.

        if ultima.tzinfo is None:

            ultima = ultima.replace(
                tzinfo=timezone.utc
            )

    except Exception:

        print(
            "La fecha anterior no es válida."
        )

        print(
            "Se realizará una actualización."
        )

        return True

    # --------------------------------------------------------
    # CALCULAR DIFERENCIA
    # --------------------------------------------------------

    diferencia = ahora - ultima

    dias = (
        diferencia.total_seconds()
        / 86400
    )

    print(
        f"Días desde última actualización CNRT: "
        f"{dias:.2f}"
    )

    # --------------------------------------------------------
    # 15 DÍAS
    # --------------------------------------------------------

    if dias >= 15:

        print(
            "Han pasado 15 días o más."
        )

        print(
            "Corresponde actualizar CNRT."
        )

        return True

    print(
        "Todavía no han pasado 15 días."
    )

    print(
        "No corresponde actualizar CNRT."
    )

    return False


# ============================================================
# GUARDAR FECHA
# ============================================================

def guardar_fecha():

    ahora = datetime.now(
        timezone.utc
    )

    ARCHIVO_FECHA.write_text(
        ahora.isoformat(),
        encoding="utf-8"
    )

    print(
        "Fecha de actualización Parque Móvil guardada:"
    )

    print(
        ahora.isoformat()
    )


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    if debe_actualizar():

        print(
            "ACTUALIZAR"
        )

    else:

        print(
            "ESPERAR"
        )
