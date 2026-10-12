import csv
import sys
from pathlib import Path

# Permite ejecutar este archivo directamente sin instalar el paquete ni definir
# PYTHONPATH. La ruta se calcula desde la ubicación real del archivo.
RAIZ_PROYECTO = Path(__file__).resolve().parent
RUTA_FUENTES = RAIZ_PROYECTO / "src"
if not RUTA_FUENTES.is_dir():
    raise SystemExit(
        "No se encontro la carpeta 'src'. Copie o descomprima el proyecto "
        "completo, no solamente ejecutar_simulacion.py."
    )
sys.path.insert(0, str(RUTA_FUENTES))

from paciente_virtual.configuracion import crear_motor_referencia


def main() -> None:
    # Se parte de CO2 elevado para verificar que la alteración se propaga
    # desde el agente nervioso hacia el respiratorio.
    motor = crear_motor_referencia(
        paso_s=0.1,
        valores_iniciales={"presion_arterial_co2": 55.0},
    )
    historial = motor.ejecutar(duracion_s=30.0)
    destino = RAIZ_PROYECTO / "resultados/simulacion.csv"
    destino.parent.mkdir(exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=historial[0].keys())
        escritor.writeheader()
        escritor.writerows(historial)
    final = historial[-1]
    print(f"Simulacion terminada: {len(historial) - 1} ciclos")
    print(f"Frecuencia cardiaca final: {final['frecuencia_cardiaca']:.2f} latido/min")
    print(f"Presion arterial media final: {final['presion_arterial_media']:.2f} mmHg")
    print(f"Presion arterial de CO2 final: {final['presion_arterial_co2']:.2f} mmHg")
    print(f"Resultado guardado en {destino}")


if __name__ == "__main__":
    main()
