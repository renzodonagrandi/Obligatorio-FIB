import argparse
import csv
import json
import sys
from pathlib import Path

# Permite ejecutar este archivo directamente sin instalar el paquete ni definir
# PYTHONPATH. La ruta se calcula desde la ubicación real del archivo.
RAIZ_PROYECTO = Path(__file__).resolve().parent
RUTA_FUENTES = RAIZ_PROYECTO / "src"
if not RUTA_FUENTES.is_dir():
    raise SystemExit(
        "No se encontro la carpeta 'src'. Copie o descomprima el proyecto "
        "completo, no solamente ejecutar_simulacion_ecg.py."
    )
sys.path.insert(0, str(RUTA_FUENTES))

from paciente_virtual.analisis import analizar_por_fases
from paciente_virtual.configuracion import crear_motor_referencia
from paciente_virtual.ecg import AgenteECG
from paciente_virtual.fuente_ecg import ErrorSenalECG, leer_csv_ecg

EVENTO_ARRITMIA = "taquiarritmia"
TOLERANCIA_TIEMPO_S = 1e-9


def ruta_del_proyecto(ruta: Path) -> Path:
    return ruta if ruta.is_absolute() else RAIZ_PROYECTO / ruta


def guardar_historial(destino: Path, historial: list[dict[str, float]]) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=historial[0].keys())
        escritor.writeheader()
        escritor.writerows(historial)


def imprimir_resumen(resumen: dict) -> None:
    print(f"Señal: {resumen['origen']} (calidad: {resumen['calidad']})")
    print(f"  Muestras: {resumen['cantidad_muestras']}  "
          f"Duración: {resumen['duracion_s']:.3f} s  "
          f"Muestreo: {resumen['frecuencia_muestreo_hz']:.2f} Hz")
    print(f"  Amplitud: {resumen['amplitud_minima_mV']:.4f} a {resumen['amplitud_maxima_mV']:.4f} mV")
    for episodio in resumen["episodios"]:
        print(f"  Episodio {episodio['evento']}: {episodio['inicio_s']:g} s a {episodio['fin_s']:g} s")
    for advertencia in resumen["advertencias"]:
        print(f"  Advertencia: {advertencia}")


def _formato(valor: float | None, tiempo: float | None = None) -> str:
    if valor is None:
        return "-"
    texto = f"{valor:.2f}"
    return texto if tiempo is None else f"{texto} @{tiempo:g}s"


def imprimir_tabla(analisis: dict[str, dict]) -> None:
    columnas = ("variable", "basal", "inicio cambio", "extremo durante",
                "fin episodio", "final", "recuperación")
    filas = []
    for variable, datos in analisis.items():
        basal = datos["basal"]
        durante = datos["durante"]
        # El extremo es el que más se aleja del basal.
        if abs(durante["maximo"] - basal) >= abs(durante["minimo"] - basal):
            extremo = _formato(durante["maximo"], durante["tiempo_maximo_s"])
        else:
            extremo = _formato(durante["minimo"], durante["tiempo_minimo_s"])
        inicio = datos["tiempo_inicio_cambio_s"]
        recuperacion = datos["tiempo_recuperacion_s"]
        filas.append((
            variable, _formato(basal),
            "-" if inicio is None else f"{inicio:g} s",
            extremo, _formato(datos["valor_fin_episodio"]), _formato(datos["final"]),
            "no se recupera" if recuperacion is None else f"{recuperacion:g} s",
        ))
    anchos = [max(len(str(f[i])) for f in (columnas, *filas)) for i in range(len(columnas))]
    print("  ".join(c.ljust(a) for c, a in zip(columnas, anchos)))
    print("  ".join("-" * a for a in anchos))
    for fila in filas:
        print("  ".join(str(c).ljust(a) for c, a in zip(fila, anchos)))


def main() -> None:
    analizador = argparse.ArgumentParser(
        description="Simula el Paciente Virtual alimentado por una señal de ECG")
    analizador.add_argument("--csv", type=Path, default=Path("resultados/ecg_simulado.csv"))
    analizador.add_argument("--duracion", type=float, default=60.0)
    analizador.add_argument("--paso", type=float, default=0.1)
    analizador.add_argument("--salida", type=Path, default=Path("resultados/simulacion_ecg.csv"))
    argumentos = analizador.parse_args()

    try:
        senal = leer_csv_ecg(ruta_del_proyecto(argumentos.csv))
    except ErrorSenalECG as error:
        print(error, file=sys.stderr)
        sys.exit(1)
    resumen = senal.resumen()
    imprimir_resumen(resumen)

    motor = crear_motor_referencia(paso_s=argumentos.paso, agentes_adicionales=[AgenteECG(senal)])
    historial = motor.ejecutar(argumentos.duracion)
    destino = ruta_del_proyecto(argumentos.salida)
    guardar_historial(destino, historial)
    print(f"\nSimulación terminada: {len(historial) - 1} ciclos de {argumentos.paso:g} s")
    print(f"Historial guardado en {destino}")

    episodio = next((e for e in senal.episodios() if e.evento == EVENTO_ARRITMIA), None)
    if episodio is None:
        print(f"\nLa señal no contiene un episodio de '{EVENTO_ARRITMIA}'; no se analiza por fases.")
        return
    print(f"\nEpisodio de {EVENTO_ARRITMIA}: {episodio.inicio_s:g} s a {episodio.fin_s:g} s")
    if historial[-1]["tiempo_s"] < episodio.fin_s - TOLERANCIA_TIEMPO_S:
        print(f"Aviso: la duración simulada ({argumentos.duracion:g} s) no cubre el fin del "
              f"episodio ({episodio.fin_s:g} s); no se analiza por fases.")
        return
    analisis = analizar_por_fases(historial, episodio.inicio_s, episodio.fin_s)
    destino_analisis = RAIZ_PROYECTO / "resultados" / "analisis_ecg.json"
    destino_analisis.parent.mkdir(exist_ok=True)
    destino_analisis.write_text(json.dumps({
        "senal": resumen,
        "paso_s": argumentos.paso,
        "duracion_s": argumentos.duracion,
        "episodio": {"evento": episodio.evento, "inicio_s": episodio.inicio_s,
                     "fin_s": episodio.fin_s},
        "variables": analisis,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    imprimir_tabla(analisis)
    print(f"\nAnálisis guardado en {destino_analisis}")


if __name__ == "__main__":
    main()
