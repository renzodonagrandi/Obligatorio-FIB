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
