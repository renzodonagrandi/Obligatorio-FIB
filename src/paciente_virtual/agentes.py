from dataclasses import dataclass
from typing import Protocol

from .estado import CalidadDato, InstantaneaEstado


@dataclass(frozen=True)
class Publicacion:
    variable: str
    valor: float
    unidad: str
    calidad: CalidadDato = CalidadDato.VALIDO


class Agente(Protocol):
    identificador: str
    entradas: frozenset[str]
    salidas: frozenset[str]

    def calcular(self, estado: InstantaneaEstado, paso_s: float) -> list[Publicacion]: ...


def acercar(valor: float, objetivo: float, rapidez: float, paso_s: float) -> float:
    """Aproximación de primer orden, estable para pasos pequeños."""
    fraccion = min(max(rapidez * paso_s, 0.0), 1.0)
    return valor + fraccion * (objetivo - valor)

