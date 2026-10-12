"""Agente integrador de ECG.

Traduce las muestras de una fuente de ECG en las dos entradas que el Paciente
Virtual ya declara (``frecuencia_cardiaca_objetivo`` y ``eficiencia_ritmo``).
No lee archivos ni dibuja: recibe cualquier objeto que cumpla
``FuenteMuestrasECG``.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .agentes import Publicacion
from .estado import CalidadDato, InstantaneaEstado
from .fuente_ecg import CalidadSenal, MuestraECG

VARIABLE_FRECUENCIA = "frecuencia_cardiaca_objetivo"
UNIDAD_FRECUENCIA = "latido/min"
VARIABLE_EFICIENCIA = "eficiencia_ritmo"
UNIDAD_EFICIENCIA = "1"
FRECUENCIA_SIN_CONTROL_EXTERNO = 0.0   # centinela documentado en el catálogo
EFICIENCIA_NEUTRA = 1.0
TOLERANCIA_TIEMPO_S = 1e-9


@runtime_checkable
class FuenteMuestrasECG(Protocol):
    """Contrato mínimo que el agente necesita de cualquier fuente de ECG.

    Lo cumple ``SenalECG`` (CSV), pero también podría cumplirlo un búfer de
    hardware, un modelo de IA o un simulador en red. Para trabajar en tiempo
    real basta con escribir una clase nueva que cumpla este contrato
    (``tiempo_final_s`` es el último tiempo con datos disponibles); el agente,
    el motor y la visualización no cambian.
    """

    @property
    def calidad(self) -> CalidadSenal: ...

    @property
    def tiempo_final_s(self) -> float: ...

    def muestras_en_intervalo(self, inicio_s: float, fin_s: float) -> Sequence[MuestraECG]: ...

    def ultima_muestra_hasta(self, tiempo_s: float) -> MuestraECG | None: ...


@dataclass(frozen=True)
class SeleccionECG:
    """Valores elegidos para un ciclo y cómo se obtuvieron."""

    frecuencia_cardiaca_lpm: float
    eficiencia_ritmo: float
    calidad: CalidadDato
    criterio: str        # "promedio_intervalo" | "retencion_ultima" | "retencion_fin_senal" | "sin_datos"
    cantidad_muestras: int   # muestras promediadas (0 si hubo retención o sin datos)


class AgenteECG:
    """Publica la frecuencia objetivo y la eficiencia del ritmo a partir de una fuente."""

    identificador = "agente_ecg"
    entradas = frozenset()
    salidas = frozenset({VARIABLE_FRECUENCIA, VARIABLE_EFICIENCIA})

    def __init__(self, fuente: FuenteMuestrasECG):
        if not isinstance(fuente, FuenteMuestrasECG):
            raise TypeError(
                f"AgenteECG necesita una fuente que cumpla FuenteMuestrasECG "
                f"(calidad, tiempo_final_s, muestras_en_intervalo y ultima_muestra_hasta); "
                f"se recibió {type(fuente).__name__}"
            )
        self._fuente = fuente

    @property
    def fuente(self) -> FuenteMuestrasECG:
        return self._fuente

    def seleccionar(self, tiempo_s: float, paso_s: float) -> SeleccionECG:
        """Elige los valores a publicar en ``tiempo_s`` para un ciclo de ``paso_s``.

        Estrategia, en este orden:
        1. Si hay muestras en (tiempo_s - paso_s, tiempo_s], publica el promedio
           aritmético de FC y de eficiencia ("promedio_intervalo"). Así cada
           muestra se usa en exactamente un ciclo, sin pérdidas ni duplicados.
        2. Si no hay muestras y tampoco hay ninguna anterior, publica valores
           neutros: FC 0.0 (sin control externo) y eficiencia 1.0 ("sin_datos").
        3. Si ``tiempo_s`` ya pasó el final de la señal, retiene la última muestra
           con calidad DEGRADADO ("retencion_fin_senal").
        4. En otro caso (paso menor que el período de muestreo), retiene la
           última muestra ("retencion_ultima").
        La calidad base es VALIDO solo si la fuente es VALIDO; si no, DEGRADADO.
        No recorta valores: el motor valida el dominio de cada variable.
        """
        fuente = self._fuente
        calidad_base = (CalidadDato.VALIDO if fuente.calidad == CalidadSenal.VALIDO
                        else CalidadDato.DEGRADADO)
        ventana = fuente.muestras_en_intervalo(tiempo_s - paso_s, tiempo_s)
        if ventana:
            return SeleccionECG(
                statistics.fmean(m.frecuencia_cardiaca_lpm for m in ventana),
                statistics.fmean(m.eficiencia_ritmo for m in ventana),
                calidad_base, "promedio_intervalo", len(ventana),
            )
        ultima = fuente.ultima_muestra_hasta(tiempo_s)
        if ultima is None:
            return SeleccionECG(FRECUENCIA_SIN_CONTROL_EXTERNO, EFICIENCIA_NEUTRA,
                                CalidadDato.VALIDO, "sin_datos", 0)
        if tiempo_s > fuente.tiempo_final_s + TOLERANCIA_TIEMPO_S:
            return SeleccionECG(ultima.frecuencia_cardiaca_lpm, ultima.eficiencia_ritmo,
                                CalidadDato.DEGRADADO, "retencion_fin_senal", 0)
        return SeleccionECG(ultima.frecuencia_cardiaca_lpm, ultima.eficiencia_ritmo,
                            calidad_base, "retencion_ultima", 0)

    def calcular(self, estado: InstantaneaEstado, paso_s: float) -> list[Publicacion]:
        seleccion = self.seleccionar(estado.tiempo_s, paso_s)
        return [
            Publicacion(VARIABLE_FRECUENCIA, seleccion.frecuencia_cardiaca_lpm,
                        UNIDAD_FRECUENCIA, seleccion.calidad),
            Publicacion(VARIABLE_EFICIENCIA, seleccion.eficiencia_ritmo,
                        UNIDAD_EFICIENCIA, seleccion.calidad),
        ]
