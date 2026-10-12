import csv
import sys
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ_PROYECTO / "src"))

from paciente_virtual.escenarios import ESCENARIOS


def guardar_csv(nombre: str, historial: list[dict[str, float]]) -> Path:
    destino = RAIZ_PROYECTO / "resultados" / f"{nombre}.csv"
    destino.parent.mkdir(exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=historial[0].keys())
        escritor.writeheader()
        escritor.writerows(historial)
    return destino


def main() -> None:
    for nombre, escenario in ESCENARIOS.items():
        motor = escenario.crear_motor()
        historial = motor.ejecutar(escenario.duracion_s)
        destino = guardar_csv(nombre, historial)
        final = historial[-1]
        print(
            f"{nombre:20s} FC={final['frecuencia_cardiaca']:6.1f} "
            f"PAM={final['presion_arterial_media']:6.1f} "
            f"PaCO2={final['presion_arterial_co2']:5.1f} -> {destino.name}"
        )


if __name__ == "__main__":
    main()
