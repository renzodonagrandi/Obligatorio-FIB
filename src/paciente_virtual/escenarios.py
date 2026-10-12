from dataclasses import dataclass

from .configuracion import crear_motor_referencia
from .motor import EventoPerturbacion, MotorSimulacion


@dataclass(frozen=True)
class Escenario:
    identificador: str
    descripcion: str
    duracion_s: float
    eventos: tuple[EventoPerturbacion, ...] = ()

    def crear_motor(self, paso_s: float = 0.1) -> MotorSimulacion:
        return crear_motor_referencia(paso_s=paso_s, eventos=list(self.eventos))


ESCENARIOS = {
    "basal": Escenario("basal", "Paciente de referencia sin perturbaciones", 60.0),
    "hemorragia": Escenario(
        "hemorragia",
        "Reduccion instantanea del volumen sanguineo a los 10 s",
        90.0,
        (EventoPerturbacion("perdida_volumen", 10.0, {"volumen_sanguineo": 4.0}),),
    ),
    "aumento_resistencia": Escenario(
        "aumento_resistencia",
        "Aumento de resistencia vascular sistemica a los 10 s",
        60.0,
        (EventoPerturbacion("vasoconstriccion", 10.0, {"resistencia_vascular_sistemica": 24.0}),),
    ),
    "hipoventilacion": Escenario(
        "hipoventilacion",
        "Reduccion sostenida de la respuesta ventilatoria",
        90.0,
        (EventoPerturbacion("depresion_respiratoria", 10.0, {"factor_ventilatorio": 0.5}),),
    ),
}


def obtener_escenario(identificador: str) -> Escenario:
    try:
        return ESCENARIOS[identificador]
    except KeyError as error:
        raise KeyError(f"Escenario desconocido: {identificador}") from error
