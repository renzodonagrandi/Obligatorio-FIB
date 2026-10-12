"""Genera, de forma reproducible, los datos que usa el informe en informe/datos/.

Uso desde la raíz del proyecto:
    .venv/bin/python3 informe/generar_resultados_informe.py
"""

import csv
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO / "src"))
sys.path.insert(0, str(RAIZ_PROYECTO))

from agente_externo_ecg import generar_archivo
from interfaz_web import VERSION_INTERFAZ
from paciente_virtual.analisis import analizar_por_fases
from paciente_virtual.configuracion import crear_motor_referencia
from paciente_virtual.ecg import AgenteECG
from paciente_virtual.fuente_ecg import leer_csv_ecg

CARPETA_DATOS = RAIZ_PROYECTO / "informe" / "datos"
RUTA_ECG = RAIZ_PROYECTO / "resultados" / "ecg_simulado.csv"
PARAMETROS_ECG = {"duracion_s": 20.0, "frecuencia_cardiaca_lpm": 70.0,
                  "inicio_arritmia_s": 5.0, "fin_arritmia_s": 14.0}
DURACION_SIMULACION_S = 60.0
PASO_S = 0.1
PASOS_SENSIBILIDAD = (0.05, 0.1, 0.2, 0.5)
PASO_REFERENCIA_SENSIBILIDAD = 0.1
EVENTO_ARRITMIA = "taquiarritmia"
VENTANAS_SELECCION = {
    "seleccion_agente_4_6s.csv": (4.5, 6.0),
    "seleccion_agente_13_15s.csv": (13.5, 14.5),
    "seleccion_agente_19_21s.csv": (19.5, 21.0),
}


def guardar_csv(nombre: str, filas: list[dict]) -> Path:
    destino = CARPETA_DATOS / nombre
    with destino.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=filas[0].keys())
        escritor.writeheader()
        escritor.writerows(filas)
    return destino


def guardar_json(nombre: str, contenido: dict) -> Path:
    destino = CARPETA_DATOS / nombre
    destino.write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destino


def simular(senal, paso_s: float, con_agente: bool = True) -> list[dict[str, float]]:
    agentes = [AgenteECG(senal)] if con_agente else None
    motor = crear_motor_referencia(paso_s=paso_s, agentes_adicionales=agentes)
    return motor.ejecutar(DURACION_SIMULACION_S)


def metricas_sensibilidad(analisis: dict) -> dict[str, float | None]:
    return {
        "fc_maxima_durante": analisis["frecuencia_cardiaca"]["durante"]["maximo"],
        "vs_minimo_durante": analisis["volumen_sistolico"]["durante"]["minimo"],
        "gc_minimo_durante": analisis["gasto_cardiaco"]["durante"]["minimo"],
        "pam_minima_durante": analisis["presion_arterial_media"]["durante"]["minimo"],
        "do2_minimo_durante": analisis["aporte_sistemico_o2"]["durante"]["minimo"],
        "pam_maxima_despues": analisis["presion_arterial_media"]["despues"]["maximo"],
        "tiempo_recuperacion_pam_s": analisis["presion_arterial_media"]["tiempo_recuperacion_s"],
    }


def diferencia_porcentual(valor: float | None, referencia: float | None) -> float | None:
    if valor is None or referencia is None or referencia == 0:
        return None
    return (valor - referencia) / abs(referencia) * 100.0


def tiempos_ventana(inicio_s: float, fin_s: float, paso_s: float) -> list[float]:
    cantidad = round((fin_s - inicio_s) / paso_s)
    return [round(inicio_s + k * paso_s, 10) for k in range(cantidad + 1)]


def commit_actual() -> dict[str, object]:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ_PROYECTO,
                                capture_output=True, text=True, check=True).stdout.strip()
        cambios = subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ_PROYECTO,
                                 capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "cambios_sin_commitear": None}
    return {"commit": commit, "cambios_sin_commitear": bool(cambios)}


def main() -> None:
    CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    generados: list[Path] = []

    # 1. Señal de entrada, regenerada con el agente externo entregado.
    generar_archivo(RUTA_ECG, **PARAMETROS_ECG)
    copia_ecg = CARPETA_DATOS / "ecg_simulado.csv"
    shutil.copyfile(RUTA_ECG, copia_ecg)
    generados.append(copia_ecg)
    senal = leer_csv_ecg(RUTA_ECG)
    episodio = next(e for e in senal.episodios() if e.evento == EVENTO_ARRITMIA)

    # 2. Simulación acoplada y análisis por fases.
    historial = simular(senal, PASO_S)
    generados.append(guardar_csv("simulacion_ecg_60s.csv", historial))
    analisis = analizar_por_fases(historial, episodio.inicio_s, episodio.fin_s)
    generados.append(guardar_json("analisis_fases_60s.json", {
        "senal": senal.resumen(), "paso_s": PASO_S, "duracion_s": DURACION_SIMULACION_S,
        "episodio": {"evento": episodio.evento, "inicio_s": episodio.inicio_s, "fin_s": episodio.fin_s},
        "variables": analisis,
    }))

    # 3. Referencia basal sin el agente ECG.
    generados.append(guardar_csv("simulacion_basal_60s.csv", simular(senal, PASO_S, con_agente=False)))

    # 4. Sensibilidad al paso temporal con la señal ECG.
    por_paso = {
        paso: metricas_sensibilidad(
            analizar_por_fases(simular(senal, paso), episodio.inicio_s, episodio.fin_s))
        for paso in PASOS_SENSIBILIDAD
    }
    referencia = por_paso[PASO_REFERENCIA_SENSIBILIDAD]
    generados.append(guardar_json("sensibilidad_paso_ecg.json", {
        "duracion_s": DURACION_SIMULACION_S,
        "episodio": {"inicio_s": episodio.inicio_s, "fin_s": episodio.fin_s},
        "paso_referencia_s": PASO_REFERENCIA_SENSIBILIDAD,
        "pasos": [
            {
                "paso_s": paso,
                "metricas": metricas,
                "diferencia_porcentual_vs_referencia": {
                    clave: diferencia_porcentual(valor, referencia[clave])
                    for clave, valor in metricas.items()
                },
            }
            for paso, metricas in por_paso.items()
        ],
    }))

    # 5. Qué selecciona el agente alrededor de los bordes del episodio y del fin de la señal.
    agente = AgenteECG(senal)
    for nombre, (inicio, fin) in VENTANAS_SELECCION.items():
        filas = []
        for tiempo in tiempos_ventana(inicio, fin, PASO_S):
            seleccion = agente.seleccionar(tiempo, PASO_S)
            filas.append({
                "tiempo_s": tiempo, "criterio": seleccion.criterio,
                "cantidad_muestras": seleccion.cantidad_muestras,
                "frecuencia_cardiaca_lpm": seleccion.frecuencia_cardiaca_lpm,
                "eficiencia_ritmo": seleccion.eficiencia_ritmo,
                "calidad": seleccion.calidad.value,
            })
        generados.append(guardar_csv(nombre, filas))

    # 6. Metadatos para poder reproducir los resultados.
    generados.append(guardar_json("metadatos.json", {
        "python": platform.python_version(),
        "version_interfaz": VERSION_INTERFAZ,
        "fecha_hora": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git": commit_actual(),
        "parametros": {
            "ecg": PARAMETROS_ECG,
            "duracion_simulacion_s": DURACION_SIMULACION_S,
            "paso_s": PASO_S,
            "pasos_sensibilidad_s": list(PASOS_SENSIBILIDAD),
            "paso_referencia_sensibilidad_s": PASO_REFERENCIA_SENSIBILIDAD,
            "ventanas_seleccion_s": {n: list(v) for n, v in VENTANAS_SELECCION.items()},
        },
    }))

    print(f"Señal: {senal.origen} ({senal.calidad.value}), episodio de {episodio.evento} "
          f"de {episodio.inicio_s:g} s a {episodio.fin_s:g} s")
    print(f"Archivos generados en {CARPETA_DATOS.relative_to(RAIZ_PROYECTO)}/:")
    for ruta in generados:
        print(f"  {ruta.name:32s} {ruta.stat().st_size:>8d} bytes")


if __name__ == "__main__":
    main()
