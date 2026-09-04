from pathlib import Path
from datetime import datetime, timezone


ARCHIVO_FECHA = Path("ultima_actualizacion.txt")


def debe_actualizar():

    ahora = datetime.now(timezone.utc)

    if not ARCHIVO_FECHA.exists():

        print(
            "No existe fecha anterior."
        )

        print(
            "Se realizará la primera actualización."
        )

        return True

    texto = ARCHIVO_FECHA.read_text(
        encoding="utf-8"
    ).strip()

    try:

        ultima = datetime.fromisoformat(
            texto
        )

    except Exception:

        print(
            "La fecha anterior no es válida."
        )

        print(
            "Se realizará una actualización."
        )

        return True

    diferencia = ahora - ultima

    dias = diferencia.total_seconds() / 86400

    print(
        f"Días desde última actualización: "
        f"{dias:.2f}"
    )

    if dias >= 15:

        print(
            "Han pasado 15 días o más."
        )

        return True

    print(
        "Todavía no han pasado 15 días."
    )

    return False


def guardar_fecha():

    ahora = datetime.now(
        timezone.utc
    )

    ARCHIVO_FECHA.write_text(
        ahora.isoformat(),
        encoding="utf-8"
    )

    print(
        f"Fecha de actualización guardada: "
        f"{ahora.isoformat()}"
    )


if __name__ == "__main__":

    if debe_actualizar():

        print("ACTUALIZAR")

    else:

        print("ESPERAR")
