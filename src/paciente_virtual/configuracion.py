from collections.abc import Sequence

from .agentes import Agente
from .estado import EstadoFisiologicoGlobal, ValorFisiologico
from .modelos import AgenteCardiovascular, AgenteNervioso, AgenteRespiratorio
from .motor import DefinicionVariable, EventoPerturbacion, MotorSimulacion


CATALOGO = {
    "frecuencia_cardiaca": DefinicionVariable("latido/min", 0.0, 300.0),
    "volumen_sistolico": DefinicionVariable("mL/latido", 0.0, 250.0),
    "gasto_cardiaco": DefinicionVariable("L/min", 0.0, 30.0),
    "aporte_sistemico_o2": DefinicionVariable("mL/min", 0.0, 5000.0),
    "presion_arterial_media": DefinicionVariable("mmHg", 0.0, 250.0),
    "volumen_sanguineo": DefinicionVariable("L", 1.0, 10.0),
    "contractilidad": DefinicionVariable("1", 0.1, 3.0),
    "frecuencia_cardiaca_objetivo": DefinicionVariable("latido/min", 0.0, 240.0),
    "eficiencia_ritmo": DefinicionVariable("1", 0.2, 1.2),
    "resistencia_vascular_sistemica": DefinicionVariable("mmHg min/L", 1.0, 50.0),
    "frecuencia_respiratoria": DefinicionVariable("respiracion/min", 0.0, 100.0),
    "factor_ventilatorio": DefinicionVariable("1", 0.1, 3.0),
    "hemoglobina": DefinicionVariable("g/dL", 3.0, 25.0),
    "bicarbonato": DefinicionVariable("mmol/L", 3.0, 50.0),
    "ventilacion_minuto": DefinicionVariable("L/min", 0.0, 40.0),
    "ventilacion_alveolar": DefinicionVariable("L/min", 0.0, 35.0),
    "presion_arterial_co2": DefinicionVariable("mmHg", 0.0, 200.0),
    "presion_arterial_o2": DefinicionVariable("mmHg", 0.0, 700.0),
    "saturacion_arterial_o2": DefinicionVariable("%", 0.0, 100.0),
    "contenido_arterial_o2": DefinicionVariable("mL/dL", 0.0, 35.0),
    "ph_arterial": DefinicionVariable("1", 6.5, 8.0),
    "actividad_simpatica": DefinicionVariable("1", 0.0, 3.0),
    "actividad_parasimpatica": DefinicionVariable("1", 0.0, 2.0),
    "impulso_respiratorio": DefinicionVariable("1", 0.0, 3.0),
}


def crear_motor_referencia(paso_s: float = 0.1, valores_iniciales: dict[str, float] | None = None,
                           eventos: list[EventoPerturbacion] | None = None,
                           agentes_adicionales: Sequence[Agente] | None = None) -> MotorSimulacion:
    """Crea el motor de referencia.

    ``agentes_adicionales`` permite registrar agentes externos (por ejemplo
    ``AgenteECG``) después de los tres agentes fisiológicos de base.
    """
    iniciales = {
        "frecuencia_cardiaca": ValorFisiologico(70.0, "latido/min"),
        "volumen_sistolico": ValorFisiologico(70.0, "mL/latido"),
        "gasto_cardiaco": ValorFisiologico(4.9, "L/min"),
        "aporte_sistemico_o2": ValorFisiologico(970.0, "mL/min"),
        "presion_arterial_media": ValorFisiologico(90.2, "mmHg"),
        "volumen_sanguineo": ValorFisiologico(5.0, "L"),
        "contractilidad": ValorFisiologico(1.0, "1"),
        "frecuencia_cardiaca_objetivo": ValorFisiologico(0.0, "latido/min"),
        "eficiencia_ritmo": ValorFisiologico(1.0, "1"),
        "resistencia_vascular_sistemica": ValorFisiologico(18.0, "mmHg min/L"),
        "frecuencia_respiratoria": ValorFisiologico(12.0, "respiracion/min"),
        "factor_ventilatorio": ValorFisiologico(1.0, "1"),
        "hemoglobina": ValorFisiologico(15.0, "g/dL"),
        "bicarbonato": ValorFisiologico(24.0, "mmol/L"),
        "ventilacion_minuto": ValorFisiologico(6.0, "L/min"),
        "ventilacion_alveolar": ValorFisiologico(4.32, "L/min"),
        "presion_arterial_co2": ValorFisiologico(40.0, "mmHg"),
        "presion_arterial_o2": ValorFisiologico(90.0, "mmHg"),
        "saturacion_arterial_o2": ValorFisiologico(97.0, "%"),
        "contenido_arterial_o2": ValorFisiologico(19.8, "mL/dL"),
        "ph_arterial": ValorFisiologico(7.40, "1"),
        "actividad_simpatica": ValorFisiologico(1.0, "1"),
        "actividad_parasimpatica": ValorFisiologico(1.0, "1"),
        "impulso_respiratorio": ValorFisiologico(1.0, "1"),
    }
    for nombre, valor in (valores_iniciales or {}).items():
        if nombre not in iniciales:
            raise KeyError(f"Variable inicial desconocida: {nombre}")
        anterior = iniciales[nombre]
        iniciales[nombre] = ValorFisiologico(valor, anterior.unidad)
    agentes = [AgenteNervioso(), AgenteCardiovascular(), AgenteRespiratorio(),
               *(agentes_adicionales or ())]
    return MotorSimulacion(EstadoFisiologicoGlobal(iniciales), agentes, CATALOGO, paso_s, eventos)
