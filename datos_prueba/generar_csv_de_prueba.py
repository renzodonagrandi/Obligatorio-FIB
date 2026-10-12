"""Genera los CSV de prueba (válidos, degradado e inválidos) en datos_prueba/.

Uso desde la raíz del proyecto:
    .venv/bin/python3 datos_prueba/generar_csv_de_prueba.py
"""

import csv
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ_PROYECTO = CARPETA.parent
sys.path.insert(0, str(RAIZ_PROYECTO))

from agente_externo_ecg import generar_archivo

ENCABEZADO = ["tiempo_s", "ecg_mV", "frecuencia_cardiaca_lpm", "eficiencia_ritmo", "evento"]


def filas_basicas(cantidad: int = 10) -> list[list]:
    """Filas válidas a 250 Hz para armar los casos inválidos pequeños."""
    return [[round(i * 0.004, 6), 0.0, 70.0, 1.0, "ritmo_basal"] for i in range(cantidad)]


def escribir(nombre: str, encabezado: list[str], filas: list[list]) -> Path:
    ruta = CARPETA / nombre
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(encabezado)
        escritor.writerows(filas)
    return ruta


def leer(ruta: Path) -> tuple[list[str], list[list[str]]]:
    with ruta.open(newline="", encoding="utf-8") as archivo:
        filas = list(csv.reader(archivo))
    return filas[0], filas[1:]


def main() -> None:
    valido_20 = CARPETA / "ecg_valido_20s.csv"
    generar_archivo(valido_20, 20.0, 70.0, 5.0, 14.0)
    generar_archivo(CARPETA / "ecg_valido_30s_arritmia_8_20.csv", 30.0, 70.0, 8.0, 20.0)
    generados = [valido_20, CARPETA / "ecg_valido_30s_arritmia_8_20.csv"]

    encabezado, filas = leer(valido_20)
    # Hueco de muestras entre t=10.0 y t=10.1 (sin incluir los extremos).
    con_hueco = [f for f in filas if not 10.0 < float(f[0]) < 10.1]
    generados.append(escribir("ecg_degradado_hueco.csv", encabezado, con_hueco))

    columna = encabezado.index("eficiencia_ritmo")
    generados.append(escribir(
        "ecg_invalido_falta_columna.csv",
        [c for i, c in enumerate(encabezado) if i != columna],
        [[v for i, v in enumerate(f) if i != columna] for f in filas],
    ))

    tiempos = filas_basicas()
    tiempos[4][0] = tiempos[3][0]   # tiempo repetido
    tiempos[7][0] = 0.002           # tiempo desordenado
    generados.append(escribir("ecg_invalido_tiempos.csv", ENCABEZADO, tiempos))

    rangos = filas_basicas()
    rangos[3][2] = 300.0            # frecuencia fuera de rango
    rangos[6][3] = 0.1              # eficiencia fuera de rango
    generados.append(escribir("ecg_invalido_rangos.csv", ENCABEZADO, rangos))

    texto = filas_basicas()
    texto[2][1] = "abc"             # valor no numérico
    texto[5][2] = ""                # celda vacía
    generados.append(escribir("ecg_invalido_texto.csv", ENCABEZADO, texto))

    generados.append(escribir("ecg_invalido_una_muestra.csv", ENCABEZADO, filas_basicas(1)))

    for ruta in generados:
        print(f"{ruta.relative_to(RAIZ_PROYECTO)}  ({ruta.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
