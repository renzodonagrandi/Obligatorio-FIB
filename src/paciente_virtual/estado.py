from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class CalidadDato(str, Enum):
    VALIDO = "valido"
    ESTIMADO = "estimado"
    DEGRADADO = "degradado"
    NO_DISPONIBLE = "no_disponible"


@dataclass(frozen=True)
class ValorFisiologico:
    valor: float
    unidad: str
    calidad: CalidadDato = CalidadDato.VALIDO
    productor: str = "condicion_inicial"


@dataclass(frozen=True)
class InstantaneaEstado:
    ciclo: int
    tiempo_s: float
    variables: Mapping[str, ValorFisiologico]

    def obtener(self, nombre: str) -> float:
        try:
            dato = self.variables[nombre]
        except KeyError as error:
            raise KeyError(f"Variable requerida ausente: {nombre}") from error
        if dato.calidad == CalidadDato.NO_DISPONIBLE:
            raise ValueError(f"Variable no disponible: {nombre}")
        return dato.valor


class EstadoFisiologicoGlobal:
    """Conserva el último estado confirmado y genera vistas inmutables."""

    def __init__(self, valores_iniciales: Mapping[str, ValorFisiologico]):
        self._variables = dict(valores_iniciales)
        self.ciclo = 0
        self.tiempo_s = 0.0

    def instantanea(self) -> InstantaneaEstado:
        copia = MappingProxyType(dict(self._variables))
        return InstantaneaEstado(self.ciclo, self.tiempo_s, copia)

    def confirmar(self, publicaciones: Mapping[str, ValorFisiologico], paso_s: float) -> None:
        siguiente = dict(self._variables)
        siguiente.update(publicaciones)
        self._variables = siguiente
        self.ciclo += 1
        self.tiempo_s = round(self.tiempo_s + paso_s, 12)

    def aplicar_evento(self, cambios: Mapping[str, ValorFisiologico]) -> None:
        """Aplica entradas externas sin avanzar el reloj de simulación."""
        siguiente = dict(self._variables)
        siguiente.update(cambios)
        self._variables = siguiente
