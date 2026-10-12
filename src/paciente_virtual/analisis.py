from typing import Iterable

VARIABLES_CLAVE = ("frecuencia_cardiaca", "presion_arterial_media", "gasto_cardiaco",
                   "presion_arterial_co2", "presion_arterial_o2", "saturacion_arterial_o2",
                   "ph_arterial", "actividad_simpatica", "actividad_parasimpatica",
                   "aporte_sistemico_o2")


def analizar_historial(historial: list[dict[str, float]], eventos: Iterable[dict]) -> dict:
    if not historial:
        raise ValueError("No hay datos para analizar")
    eventos = list(eventos)
    tiempo_ref = min((e["tiempo_s"] for e in eventos), default=historial[0]["tiempo_s"])
    referencia = min(historial, key=lambda f: abs(f["tiempo_s"] - tiempo_ref))
    metricas = {}
    for variable in VARIABLES_CLAVE:
        if variable not in historial[0]:
            continue
        valores = [f[variable] for f in historial]
        minimo, maximo = min(valores), max(valores)
        basal, final = referencia[variable], valores[-1]
        desviacion = max(abs(minimo - basal), abs(maximo - basal))
        recuperacion = 100.0 if not eventos or desviacion == 0 else max(0.0, min(100.0, 100.0 * (1.0 - abs(final - basal) / desviacion)))
        metricas[variable] = {
            "basal": basal, "minimo": minimo,
            "tiempo_minimo_s": historial[valores.index(minimo)]["tiempo_s"],
            "maximo": maximo, "tiempo_maximo_s": historial[valores.index(maximo)]["tiempo_s"],
            "final": final,
            "cambio_final_porcentaje": 0.0 if basal == 0 else 100.0 * (final - basal) / abs(basal),
            "recuperacion_porcentaje": recuperacion,
        }
    return {"metricas": metricas, "resumen": _crear_resumen(metricas, eventos)}


def _crear_resumen(m: dict, eventos: list[dict]) -> list[str]:
    textos = [f"Se aplicaron {len(eventos)} evento(s): " + ", ".join(e["nombre"] for e in eventos) + "."] if eventos else ["Ejecución basal sin perturbaciones."]
    if (x := m.get("presion_arterial_media")) and x["minimo"] < x["basal"] * 0.95:
        textos.append("La presión arterial descendió más de 5 % respecto de la referencia.")
    if (x := m.get("actividad_simpatica")) and x["maximo"] > x["basal"] * 1.05:
        textos.append("Apareció activación simpática compensatoria dentro del modelo.")
    if (x := m.get("presion_arterial_co2")) and x["maximo"] > x["basal"] + 3.0:
        textos.append("La PaCO2 aumentó y activó la respuesta ventilatoria.")
    if (x := m.get("ph_arterial")) and x["minimo"] < x["basal"] - 0.03:
        textos.append("El pH estimado disminuyó en asociación con el cambio de CO2.")
    if (x := m.get("aporte_sistemico_o2")) and x["minimo"] < x["basal"] * 0.9:
        textos.append("El aporte sistémico de oxígeno disminuyó más de 10 %.")
    return textos


VARIABLES_FASES = ("frecuencia_cardiaca", "volumen_sistolico", "gasto_cardiaco",
                   "presion_arterial_media", "aporte_sistemico_o2", "actividad_simpatica",
                   "actividad_parasimpatica", "frecuencia_cardiaca_objetivo", "eficiencia_ritmo")
TOLERANCIA_TIEMPO_S = 1e-9


def analizar_por_fases(historial: list[dict[str, float]], inicio_s: float, fin_s: float,
                       variables: Iterable[str] = VARIABLES_FASES, umbral_cambio: float = 0.01,
                       banda_recuperacion: float = 0.02) -> dict[str, dict]:
    """Compara cada variable antes, durante y después del intervalo [inicio_s, fin_s].

    Función pura: no conoce el origen de la perturbación. Los umbrales son
    fracciones del valor basal (``umbral_cambio`` detecta el inicio del cambio y
    ``banda_recuperacion`` define cuándo la variable volvió al basal).
    """
    if not historial:
        raise ValueError("No hay datos para analizar")
    if fin_s < inicio_s:
        raise ValueError("El fin del intervalo debe ser posterior a su inicio")
    if historial[-1]["tiempo_s"] < fin_s - TOLERANCIA_TIEMPO_S:
        raise ValueError(
            f"El historial termina en t={historial[-1]['tiempo_s']:g} s y no cubre el fin "
            f"del intervalo (t={fin_s:g} s)"
        )
    previas = [f for f in historial if f["tiempo_s"] <= inicio_s + TOLERANCIA_TIEMPO_S]
    if not previas:
        raise ValueError(f"El historial no tiene datos anteriores a t={inicio_s:g} s")
    fila_basal = previas[-1]
    durante = [f for f in historial
               if inicio_s - TOLERANCIA_TIEMPO_S <= f["tiempo_s"] <= fin_s + TOLERANCIA_TIEMPO_S]
    despues = [f for f in historial if f["tiempo_s"] > fin_s + TOLERANCIA_TIEMPO_S]
    fila_fin = min(historial, key=lambda f: abs(f["tiempo_s"] - fin_s))

    resultado = {}
    for variable in variables:
        if variable not in historial[0]:
            continue
        basal = fila_basal[variable]
        final = historial[-1][variable]
        umbral = umbral_cambio * abs(basal)
        inicio_cambio = next(
            (f["tiempo_s"] for f in historial
             if f["tiempo_s"] >= inicio_s - TOLERANCIA_TIEMPO_S and abs(f[variable] - basal) > umbral),
            None,
        )
        resultado[variable] = {
            "basal": basal,
            "tiempo_inicio_cambio_s": inicio_cambio,
            "durante": _extremos(durante, variable),
            "valor_fin_episodio": fila_fin[variable],
            "despues": _extremos(despues, variable),
            "final": final,
            "desviacion_final_porcentaje": None if basal == 0 else (final - basal) / basal * 100.0,
            "tiempo_recuperacion_s": _tiempo_recuperacion(
                despues, variable, basal, banda_recuperacion * abs(basal)),
        }
    return resultado


def _extremos(filas: list[dict[str, float]], variable: str) -> dict | None:
    if not filas:
        return None
    minima = min(filas, key=lambda f: f[variable])
    maxima = max(filas, key=lambda f: f[variable])
    return {"minimo": minima[variable], "tiempo_minimo_s": minima["tiempo_s"],
            "maximo": maxima[variable], "tiempo_maximo_s": maxima["tiempo_s"]}


def _tiempo_recuperacion(filas: list[dict[str, float]], variable: str, basal: float,
                         banda: float) -> float | None:
    """Primer tiempo desde el cual la variable queda dentro de la banda hasta el final."""
    tiempo = None
    for fila in reversed(filas):
        if abs(fila[variable] - basal) > banda:
            break
        tiempo = fila["tiempo_s"]
    return tiempo
