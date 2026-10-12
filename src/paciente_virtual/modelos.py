"""Modelos educativos del prototipo; no destinados a uso clínico."""

from dataclasses import dataclass
from math import log10

from .agentes import Publicacion, acercar
from .estado import InstantaneaEstado


@dataclass(frozen=True)
class ParametrosNerviosos:
    presion_referencia_mmhg: float = 90.2
    co2_referencia_mmhg: float = 40.0
    umbral_hipoxia_mmhg: float = 80.0
    ganancia_barorreflejo_simpatica: float = 1.0 / 20.0
    ganancia_barorreflejo_parasimpatica: float = 0.8 / 20.0
    ganancia_co2_respiratoria: float = 0.06
    ganancia_hipoxia_respiratoria: float = 0.015
    ganancia_quimica_simpatica: float = 0.25
    constante_tiempo_simpatica_s: float = 4.0
    constante_tiempo_parasimpatica_s: float = 1.0
    constante_tiempo_respiratoria_s: float = 2.0


class AgenteNervioso:
    identificador = "nervioso"
    entradas = frozenset({"presion_arterial_media", "presion_arterial_co2", "presion_arterial_o2"})
    salidas = frozenset({"actividad_simpatica", "actividad_parasimpatica", "impulso_respiratorio"})

    def __init__(self, parametros: ParametrosNerviosos | None = None):
        self.parametros = parametros or ParametrosNerviosos()

    def calcular(self, estado: InstantaneaEstado, paso_s: float) -> list[Publicacion]:
        p = self.parametros
        presion = estado.obtener("presion_arterial_media")
        co2 = estado.obtener("presion_arterial_co2")
        o2 = estado.obtener("presion_arterial_o2")
        simpatica_actual = estado.obtener("actividad_simpatica")
        parasimpatica_actual = estado.obtener("actividad_parasimpatica")
        impulso_actual = estado.obtener("impulso_respiratorio")

        error_presion = p.presion_referencia_mmhg - presion
        exceso_co2 = co2 - p.co2_referencia_mmhg
        deficit_o2 = max(0.0, p.umbral_hipoxia_mmhg - o2)
        estimulo_quimico = max(0.0, p.ganancia_co2_respiratoria * exceso_co2) + p.ganancia_hipoxia_respiratoria * deficit_o2

        objetivo_simpatica = limitar(
            1.0 + p.ganancia_barorreflejo_simpatica * error_presion
            + p.ganancia_quimica_simpatica * estimulo_quimico, 0.0, 3.0
        )
        objetivo_parasimpatica = limitar(
            1.0 - p.ganancia_barorreflejo_parasimpatica * error_presion, 0.0, 2.0
        )
        objetivo_impulso = limitar(1.0 + p.ganancia_co2_respiratoria * exceso_co2
                                  + p.ganancia_hipoxia_respiratoria * deficit_o2, 0.2, 3.0)
        simpatica = acercar(simpatica_actual, objetivo_simpatica, 1.0 / p.constante_tiempo_simpatica_s, paso_s)
        parasimpatica = acercar(parasimpatica_actual, objetivo_parasimpatica, 1.0 / p.constante_tiempo_parasimpatica_s, paso_s)
        impulso = acercar(impulso_actual, objetivo_impulso, 1.0 / p.constante_tiempo_respiratoria_s, paso_s)
        return [
            Publicacion("actividad_simpatica", simpatica, "1"),
            Publicacion("actividad_parasimpatica", parasimpatica, "1"),
            Publicacion("impulso_respiratorio", impulso, "1"),
        ]


@dataclass(frozen=True)
class ParametrosCardiovasculares:
    frecuencia_basal_lpm: float = 70.0
    volumen_sistolico_basal_ml: float = 70.0
    volumen_sanguineo_referencia_l: float = 5.0
    resistencia_referencia_mmhg_min_l: float = 18.0
    presion_venosa_central_mmhg: float = 2.0
    ganancia_simpatica_frecuencia: float = 25.0
    constante_tiempo_frecuencia_s: float = 3.0
    constante_tiempo_presion_s: float = 2.0


class AgenteCardiovascular:
    identificador = "cardiovascular"
    entradas = frozenset({
        "actividad_simpatica", "actividad_parasimpatica", "saturacion_arterial_o2", "volumen_sanguineo",
        "contractilidad", "resistencia_vascular_sistemica", "contenido_arterial_o2",
        "frecuencia_cardiaca_objetivo", "eficiencia_ritmo",
    })
    salidas = frozenset({
        "frecuencia_cardiaca", "volumen_sistolico", "gasto_cardiaco",
        "presion_arterial_media", "aporte_sistemico_o2",
    })

    def __init__(self, parametros: ParametrosCardiovasculares | None = None):
        self.parametros = parametros or ParametrosCardiovasculares()

    def calcular(self, estado: InstantaneaEstado, paso_s: float) -> list[Publicacion]:
        p = self.parametros
        simpatica = estado.obtener("actividad_simpatica")
        parasimpatica = estado.obtener("actividad_parasimpatica")
        saturacion = estado.obtener("saturacion_arterial_o2")
        volumen_sanguineo = estado.obtener("volumen_sanguineo")
        contractilidad = estado.obtener("contractilidad")
        resistencia = estado.obtener("resistencia_vascular_sistemica")
        contenido_o2 = estado.obtener("contenido_arterial_o2")
        frecuencia_externa = estado.obtener("frecuencia_cardiaca_objetivo")
        eficiencia_ritmo = estado.obtener("eficiencia_ritmo")
        frecuencia_actual = estado.obtener("frecuencia_cardiaca")
        presion_actual = estado.obtener("presion_arterial_media")

        estimulo_hipoxia = max(0.0, 95.0 - saturacion)
        objetivo_frecuencia = limitar(
            p.frecuencia_basal_lpm + p.ganancia_simpatica_frecuencia * (simpatica - 1.0)
            - 15.0 * (parasimpatica - 1.0)
            + 1.0 * estimulo_hipoxia, 30.0, 220.0
        )
        if frecuencia_externa > 0.0:
            objetivo_frecuencia = limitar(frecuencia_externa, 30.0, 220.0)
        frecuencia = acercar(
            frecuencia_actual, objetivo_frecuencia,
            1.0 / p.constante_tiempo_frecuencia_s, paso_s
        )

        factor_precarga = limitar(volumen_sanguineo / p.volumen_sanguineo_referencia_l, 0.3, 1.4)
        factor_poscarga = (p.resistencia_referencia_mmhg_min_l / max(resistencia, 1.0)) ** 0.25
        contractilidad_efectiva = contractilidad * (1.0 + 0.25 * (simpatica - 1.0))
        volumen_sistolico = limitar(
            p.volumen_sistolico_basal_ml * factor_precarga * contractilidad_efectiva
            * factor_poscarga * eficiencia_ritmo,
            10.0, 180.0
        )
        gasto_cardiaco = frecuencia * volumen_sistolico / 1000.0
        aporte_oxigeno = gasto_cardiaco * contenido_o2 * 10.0
        objetivo_presion = p.presion_venosa_central_mmhg + gasto_cardiaco * resistencia
        presion = acercar(
            presion_actual, objetivo_presion,
            1.0 / p.constante_tiempo_presion_s, paso_s
        )
        return [
            Publicacion("frecuencia_cardiaca", frecuencia, "latido/min"),
            Publicacion("volumen_sistolico", volumen_sistolico, "mL/latido"),
            Publicacion("gasto_cardiaco", gasto_cardiaco, "L/min"),
            Publicacion("aporte_sistemico_o2", aporte_oxigeno, "mL/min"),
            Publicacion("presion_arterial_media", presion, "mmHg"),
        ]


@dataclass(frozen=True)
class ParametrosRespiratorios:
    volumen_corriente_l: float = 0.50
    espacio_muerto_l: float = 0.14
    produccion_co2_l_min: float = 0.20
    fraccion_inspirada_o2: float = 0.21
    presion_barometrica_mmhg: float = 760.0
    presion_vapor_agua_mmhg: float = 47.0
    cociente_respiratorio: float = 0.80
    gradiente_alveolo_arterial_mmhg: float = 10.0
    constante_ventilacion_co2: float = 863.0
    constante_tiempo_co2_s: float = 12.0
    p50_oxigeno_mmhg: float = 26.8
    coeficiente_hill: float = 2.7


class AgenteRespiratorio:
    identificador = "respiratorio"
    entradas = frozenset({"impulso_respiratorio", "factor_ventilatorio", "hemoglobina", "bicarbonato"})
    salidas = frozenset({
        "frecuencia_respiratoria", "ventilacion_minuto", "ventilacion_alveolar",
        "presion_arterial_co2", "presion_arterial_o2", "saturacion_arterial_o2",
        "contenido_arterial_o2", "ph_arterial",
    })

    def __init__(self, parametros: ParametrosRespiratorios | None = None):
        self.parametros = parametros or ParametrosRespiratorios()
        if self.parametros.volumen_corriente_l <= self.parametros.espacio_muerto_l:
            raise ValueError("El volumen corriente debe superar el espacio muerto")

    def calcular(self, estado: InstantaneaEstado, paso_s: float) -> list[Publicacion]:
        """Calcula ventilación y gases con un modelo alveolar de un compartimento.

        PaCO2 objetivo se obtiene de 863*VCO2/VA. El acercamiento de primer
        orden representa el almacenamiento corporal de CO2. PAO2 usa la forma
        simplificada de la ecuación alveolar; PaO2 descuenta un gradiente fijo.
        La SaO2 se aproxima con Hill. Los supuestos quedan en los parámetros.
        """
        p = self.parametros
        impulso = estado.obtener("impulso_respiratorio")
        factor_ventilatorio = estado.obtener("factor_ventilatorio")
        hemoglobina = estado.obtener("hemoglobina")
        bicarbonato = estado.obtener("bicarbonato")
        frecuencia_actual = estado.obtener("frecuencia_respiratoria")
        co2_actual = estado.obtener("presion_arterial_co2")
        objetivo_frecuencia = limitar(12.0 * impulso * factor_ventilatorio, 2.0, 60.0)
        frecuencia = acercar(frecuencia_actual, objetivo_frecuencia, 0.8, paso_s)
        ventilacion_minuto = p.volumen_corriente_l * frecuencia
        ventilacion_alveolar = (p.volumen_corriente_l - p.espacio_muerto_l) * frecuencia

        objetivo_co2 = p.constante_ventilacion_co2 * p.produccion_co2_l_min / ventilacion_alveolar
        rapidez_co2 = 1.0 / p.constante_tiempo_co2_s
        co2 = acercar(co2_actual, objetivo_co2, rapidez_co2, paso_s)

        oxigeno_alveolar = (
            p.fraccion_inspirada_o2 * (p.presion_barometrica_mmhg - p.presion_vapor_agua_mmhg)
            - co2 / p.cociente_respiratorio
        )
        oxigeno_arterial = limitar(oxigeno_alveolar - p.gradiente_alveolo_arterial_mmhg, 1.0, 700.0)
        potencia = oxigeno_arterial ** p.coeficiente_hill
        saturacion = 100.0 * potencia / (potencia + p.p50_oxigeno_mmhg ** p.coeficiente_hill)
        contenido_oxigeno = 1.34 * hemoglobina * (saturacion / 100.0) + 0.003 * oxigeno_arterial
        ph_arterial = 6.1 + log10(bicarbonato / (0.03 * max(co2, 0.1)))
        return [
            Publicacion("frecuencia_respiratoria", frecuencia, "respiracion/min"),
            Publicacion("ventilacion_minuto", ventilacion_minuto, "L/min"),
            Publicacion("ventilacion_alveolar", ventilacion_alveolar, "L/min"),
            Publicacion("presion_arterial_co2", co2, "mmHg"),
            Publicacion("presion_arterial_o2", oxigeno_arterial, "mmHg"),
            Publicacion("saturacion_arterial_o2", saturacion, "%"),
            Publicacion("contenido_arterial_o2", contenido_oxigeno, "mL/dL"),
            Publicacion("ph_arterial", ph_arterial, "1"),
        ]


def limitar(valor: float, minimo: float, maximo: float) -> float:
    return min(max(valor, minimo), maximo)
