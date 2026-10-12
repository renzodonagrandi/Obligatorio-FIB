"""Agente externo entregado: genera un ECG con una arritmia."""

import argparse
import csv
import math
from pathlib import Path

def generar_archivo(ruta: Path, duracion_s: float, frecuencia_cardiaca_lpm: float,
                    inicio_arritmia_s: float, fin_arritmia_s: float) -> None:
    if duracion_s <= 0 or not 20 <= frecuencia_cardiaca_lpm <= 240:
        raise ValueError("Revise la duración y la frecuencia cardíaca")
    frecuencia_muestreo_hz = 250.0
    cantidad = int(duracion_s * frecuencia_muestreo_hz) + 1

    def gaussiana(valor: float, centro: float, ancho: float) -> float:
        return math.exp(-0.5 * ((valor - centro) / ancho) ** 2)

    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow([
            "tiempo_s", "ecg_mV", "frecuencia_cardiaca_lpm",
            "eficiencia_ritmo", "evento",
        ])
        fase = 0.0
        for indice in range(cantidad):
            tiempo = indice / frecuencia_muestreo_hz
            hay_arritmia = inicio_arritmia_s <= tiempo < fin_arritmia_s
            if hay_arritmia:
                # Variación determinista para que todos los equipos reciban el mismo caso.
                frecuencia_instantanea = (
                    145.0 + 24.0 * math.sin(2 * math.pi * 0.73 * tiempo)
                    + 11.0 * math.sin(2 * math.pi * 1.37 * tiempo)
                )
                eficiencia = 0.45
                evento = "taquiarritmia"
            else:
                frecuencia_instantanea = frecuencia_cardiaca_lpm
                eficiencia = 1.0
                evento = "ritmo_basal"
            fase = (fase + frecuencia_instantanea / (60.0 * frecuencia_muestreo_hz)) % 1.0
            amplitud = (
                0.12 * gaussiana(fase, 0.18, 0.035)
                - 0.15 * gaussiana(fase, 0.36, 0.012)
                + 1.10 * gaussiana(fase, 0.40, 0.010)
                - 0.25 * gaussiana(fase, 0.43, 0.014)
                + 0.30 * gaussiana(fase, 0.68, 0.060)
                + 0.015 * math.sin(2 * math.pi * 0.33 * tiempo)
            )
            escritor.writerow([
                round(tiempo, 6), round(amplitud, 6),
                round(frecuencia_instantanea, 3), eficiencia, evento,
            ])


def main() -> None:
    analizador = argparse.ArgumentParser(description="Genera un ECG educativo con una taquiarritmia")
    analizador.add_argument("--salida", type=Path, default=Path("resultados/ecg_simulado.csv"))
    analizador.add_argument("--duracion", type=float, default=20.0)
    analizador.add_argument("--frecuencia-cardiaca", type=float, default=70.0)
    analizador.add_argument("--inicio-arritmia", type=float, default=5.0)
    analizador.add_argument("--fin-arritmia", type=float, default=14.0)
    argumentos = analizador.parse_args()
    if not 0 <= argumentos.inicio_arritmia < argumentos.fin_arritmia <= argumentos.duracion:
        raise ValueError("El intervalo de la arritmia debe estar dentro de la señal")
    generar_archivo(
        argumentos.salida, argumentos.duracion, argumentos.frecuencia_cardiaca,
        argumentos.inicio_arritmia, argumentos.fin_arritmia,
    )
    print(f"ECG generado en {argumentos.salida}")


if __name__ == "__main__":
    main()
