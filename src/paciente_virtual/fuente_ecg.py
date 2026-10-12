"""Lectura y validación de fuentes de ECG.

Convierte los datos nativos de una fuente (por ahora un CSV) en una
``SenalECG`` validada. No depende del motor ni de la visualización, de modo
que otra fuente (hardware, IA u otro simulador) puede reutilizar
``validar_muestras`` sin reescribir el resto del sistema.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from pathlib import Path

COLUMNAS_OBLIGATORIAS = ("tiempo_s", "ecg_mV", "frecuencia_cardiaca_lpm",
                         "eficiencia_ritmo", "evento")
COLUMNAS_NUMERICAS = COLUMNAS_OBLIGATORIAS[:4]
EVENTOS_CONOCIDOS = frozenset({"ritmo_basal", "taquiarritmia"})
RANGO_FRECUENCIA_LPM = (20.0, 240.0)   # inclusivo
RANGO_EFICIENCIA = (0.2, 1.2)          # inclusivo
TOLERANCIA_IRREGULARIDAD = 0.01        # 1 % de la mediana de Δt
FACTOR_PERDIDA_MUESTRAS = 1.5
TOLERANCIA_TIEMPO_S = 1e-9           # para comparar tiempos sin usar ==
MAXIMO_ERRORES_MOSTRADOS = 20


class CalidadSenal(str, Enum):
    """Estado de calidad de una señal."""

    VALIDO = "valido"
    DEGRADADO = "degradado"
    INCORRECTO = "incorrecto"


class ErrorSenalECG(ValueError):
    """La señal no puede usarse; reúne todos los problemas detectados."""

    def __init__(self, origen: str, errores: Iterable[str]) -> None:
        self.origen = origen
        self.errores = tuple(errores)
        super().__init__(self._mensaje())

    def _mensaje(self) -> str:
        lineas = [f"La señal '{self.origen}' no es válida:"]
        lineas.extend(f"- {error}" for error in self.errores[:MAXIMO_ERRORES_MOSTRADOS])
        restantes = len(self.errores) - MAXIMO_ERRORES_MOSTRADOS
        if restantes > 0:
            lineas.append(f"- ... y {restantes} errores más")
        return "\n".join(lineas)

    def __str__(self) -> str:
        return self._mensaje()


@dataclass(frozen=True)
class MuestraECG:
    """Una muestra de la fuente de ECG."""

    tiempo_s: float
    ecg_mV: float
    frecuencia_cardiaca_lpm: float
    eficiencia_ritmo: float
    evento: str


@dataclass(frozen=True)
class EpisodioECG:
    """Tramo contiguo de la señal con el mismo evento."""

    evento: str
    inicio_s: float
    fin_s: float


@dataclass(frozen=True)
class SenalECG:
    """Señal de ECG validada, independiente de la fuente que la produjo."""

    origen: str
    muestras: tuple[MuestraECG, ...]
    calidad: CalidadSenal
    advertencias: tuple[str, ...] = ()

    @property
    def cantidad_muestras(self) -> int:
        return len(self.muestras)

    @cached_property
    def tiempos_s(self) -> tuple[float, ...]:
        """Tiempos de las muestras; se calcula una sola vez porque se consulta en cada ciclo."""
        return tuple(muestra.tiempo_s for muestra in self.muestras)

    @property
    def tiempo_inicial_s(self) -> float:
        return self.muestras[0].tiempo_s

    @property
    def tiempo_final_s(self) -> float:
        return self.muestras[-1].tiempo_s

    @property
    def amplitudes_mV(self) -> tuple[float, ...]:
        return tuple(muestra.ecg_mV for muestra in self.muestras)

    @property
    def duracion_s(self) -> float:
        if not self.muestras:
            return 0.0
        return self.muestras[-1].tiempo_s - self.muestras[0].tiempo_s

    @property
    def frecuencia_muestreo_hz(self) -> float:
        intervalos = _intervalos(self.tiempos_s)
        if not intervalos:
            return 0.0
        mediana = statistics.median(intervalos)
        return 1.0 / mediana if mediana > 0 else 0.0

    @property
    def amplitud_minima_mV(self) -> float:
        return min(self.amplitudes_mV)

    @property
    def amplitud_maxima_mV(self) -> float:
        return max(self.amplitudes_mV)

    def muestras_en_intervalo(self, inicio_s: float, fin_s: float) -> tuple[MuestraECG, ...]:
        """Muestras con inicio_s < t <= fin_s (intervalo semiabierto, con tolerancia)."""
        tiempos = self.tiempos_s
        desde = bisect_right(tiempos, inicio_s + TOLERANCIA_TIEMPO_S)
        hasta = bisect_right(tiempos, fin_s + TOLERANCIA_TIEMPO_S)
        return self.muestras[desde:hasta]

    def ultima_muestra_hasta(self, tiempo_s: float) -> MuestraECG | None:
        """Última muestra con t <= tiempo_s (con tolerancia), o None si no hay."""
        indice = bisect_right(self.tiempos_s, tiempo_s + TOLERANCIA_TIEMPO_S)
        return self.muestras[indice - 1] if indice > 0 else None

    def episodios(self) -> tuple[EpisodioECG, ...]:
        """Agrupa las muestras contiguas que comparten el mismo evento."""
        if not self.muestras:
            return ()
        episodios = []
        inicio = self.muestras[0]
        for muestra in self.muestras[1:]:
            if muestra.evento != inicio.evento:
                episodios.append(EpisodioECG(inicio.evento, inicio.tiempo_s, muestra.tiempo_s))
                inicio = muestra
        episodios.append(EpisodioECG(inicio.evento, inicio.tiempo_s, self.muestras[-1].tiempo_s))
        return tuple(episodios)

    def resumen(self) -> dict:
        """Metadatos de la señal (sin las muestras), serializables a JSON."""
        return {
            "origen": self.origen,
            "calidad": self.calidad.value,
            "cantidad_muestras": self.cantidad_muestras,
            "duracion_s": self.duracion_s,
            "frecuencia_muestreo_hz": self.frecuencia_muestreo_hz,
            "amplitud_minima_mV": self.amplitud_minima_mV,
            "amplitud_maxima_mV": self.amplitud_maxima_mV,
            "advertencias": list(self.advertencias),
            "episodios": [
                {"evento": e.evento, "inicio_s": e.inicio_s, "fin_s": e.fin_s}
                for e in self.episodios()
            ],
        }


def _intervalos(tiempos: Sequence[float]) -> list[float]:
    return [actual - anterior for anterior, actual in zip(tiempos, tiempos[1:])]


def _formatear_rango(rango: tuple[float, float]) -> str:
    return f"[{rango[0]:g}, {rango[1]:g}]"


def _revisar_muestras(muestras: Sequence[MuestraECG],
                      ubicaciones: Sequence[str]) -> tuple[list[str], list[str]]:
    """Devuelve (errores, advertencias); ``ubicaciones`` describe cada muestra."""
    errores: list[str] = []
    advertencias: list[str] = []
    if len(muestras) < 2:
        errores.append(f"se necesitan al menos 2 muestras válidas y hay {len(muestras)}")

    tiempo_anterior: float | None = None
    eventos_desconocidos: dict[str, int] = {}
    for muestra, ubicacion in zip(muestras, ubicaciones):
        no_finitos = [
            nombre for nombre in COLUMNAS_NUMERICAS
            if not math.isfinite(getattr(muestra, nombre))
        ]
        for nombre in no_finitos:
            errores.append(f"valor no finito en '{nombre}' en la {ubicacion}")

        tiempo = muestra.tiempo_s
        if "tiempo_s" not in no_finitos:
            if tiempo < 0:
                errores.append(f"tiempo negativo en la {ubicacion} (t={tiempo:g})")
            if tiempo_anterior is not None:
                if tiempo == tiempo_anterior:
                    errores.append(f"tiempo repetido en la {ubicacion} (t={tiempo:g})")
                elif tiempo < tiempo_anterior:
                    errores.append(
                        f"tiempos desordenados en la {ubicacion} "
                        f"(t={tiempo:g} es menor que el anterior t={tiempo_anterior:g})"
                    )
            tiempo_anterior = tiempo

        frecuencia = muestra.frecuencia_cardiaca_lpm
        minimo, maximo = RANGO_FRECUENCIA_LPM
        if "frecuencia_cardiaca_lpm" not in no_finitos and not minimo <= frecuencia <= maximo:
            errores.append(
                f"frecuencia_cardiaca_lpm={frecuencia:g} fuera del rango permitido "
                f"{_formatear_rango(RANGO_FRECUENCIA_LPM)} en la {ubicacion}"
            )
        eficiencia = muestra.eficiencia_ritmo
        minimo, maximo = RANGO_EFICIENCIA
        if "eficiencia_ritmo" not in no_finitos and not minimo <= eficiencia <= maximo:
            errores.append(
                f"eficiencia_ritmo={eficiencia:g} fuera del rango permitido "
                f"{_formatear_rango(RANGO_EFICIENCIA)} en la {ubicacion}"
            )

        if not muestra.evento.strip():
            errores.append(f"valor vacío en 'evento' en la {ubicacion}")
        elif muestra.evento not in EVENTOS_CONOCIDOS:
            eventos_desconocidos[muestra.evento] = eventos_desconocidos.get(muestra.evento, 0) + 1

    for evento, cantidad in eventos_desconocidos.items():
        advertencias.append(f"evento desconocido '{evento}' en {cantidad} muestra(s)")

    if not errores:
        advertencias.extend(_revisar_muestreo([m.tiempo_s for m in muestras]))
    return errores, advertencias


def _revisar_muestreo(tiempos: Sequence[float]) -> list[str]:
    """Advierte sobre muestreo irregular y posibles pérdidas de muestras."""
    intervalos = _intervalos(tiempos)
    mediana = statistics.median(intervalos)
    advertencias = []
    irregulares = [
        dt for dt in intervalos
        if abs(dt - mediana) > TOLERANCIA_IRREGULARIDAD * mediana
    ]
    if irregulares:
        advertencias.append(
            f"muestreo irregular: {len(irregulares)} intervalo(s) se apartan más del "
            f"{TOLERANCIA_IRREGULARIDAD:.0%} de la mediana (Δt={mediana:g} s)"
        )
    for anterior, actual in zip(tiempos, tiempos[1:]):
        if actual - anterior > FACTOR_PERDIDA_MUESTRAS * mediana:
            advertencias.append(
                f"posible pérdida de muestras entre t={anterior:g} s y t={actual:g} s"
            )
    return advertencias


def _crear_senal(muestras: Sequence[MuestraECG], origen: str,
                 ubicaciones: Sequence[str], errores_previos: Sequence[str] = ()) -> SenalECG:
    errores, advertencias = _revisar_muestras(muestras, ubicaciones)
    errores = [*errores_previos, *errores]
    if errores:
        raise ErrorSenalECG(origen, errores)
    calidad = CalidadSenal.DEGRADADO if advertencias else CalidadSenal.VALIDO
    return SenalECG(origen, tuple(muestras), calidad, tuple(advertencias))


def validar_muestras(muestras: Iterable[MuestraECG], origen: str) -> SenalECG:
    """Valida muestras de cualquier fuente y devuelve la señal o lanza ErrorSenalECG."""
    muestras = tuple(muestras)
    ubicaciones = [f"muestra {indice}" for indice in range(1, len(muestras) + 1)]
    return _crear_senal(muestras, origen, ubicaciones)


def _convertir_numero(valor: str, columna: str, linea: int) -> tuple[float | None, str | None]:
    """Devuelve (número, None) o (None, mensaje de error)."""
    if not valor:
        return None, f"línea {linea}: valor vacío en '{columna}'"
    try:
        numero = float(valor)
    except ValueError:
        numero = None
    if numero is None or not math.isfinite(numero):
        mensaje = f"línea {linea}: '{valor}' no es un número válido en '{columna}'"
        if "," in valor:
            mensaje += " (use punto como separador decimal)"
        return None, mensaje
    return numero, None


def interpretar_csv_ecg(texto: str, origen: str) -> SenalECG:
    """Interpreta el contenido de un CSV de ECG y devuelve la señal validada."""
    texto = texto.removeprefix("﻿")
    if not texto.strip():
        raise ErrorSenalECG(origen, ["el archivo está vacío o no tiene encabezado"])

    lector = csv.DictReader(io.StringIO(texto))
    if not lector.fieldnames:
        raise ErrorSenalECG(origen, ["el archivo está vacío o no tiene encabezado"])
    lector.fieldnames = [nombre.strip() for nombre in lector.fieldnames]
    encabezado = ",".join(lector.fieldnames)
    if len(lector.fieldnames) == 1 and ";" in encabezado:
        raise ErrorSenalECG(origen, [
            "línea 1: el encabezado usa ';' como separador; el separador debe ser ','"
        ])
    faltantes = [c for c in COLUMNAS_OBLIGATORIAS if c not in lector.fieldnames]
    if faltantes:
        raise ErrorSenalECG(origen, [
            "línea 1: faltan columnas obligatorias: " + ", ".join(f"'{c}'" for c in faltantes)
        ])

    errores: list[str] = []
    muestras: list[MuestraECG] = []
    ubicaciones: list[str] = []
    for fila in lector:
        linea = lector.line_num
        errores_fila = []
        if fila.get(None):
            errores_fila.append(
                f"línea {linea}: la fila tiene más campos que el encabezado "
                f"({len(lector.fieldnames) + len(fila[None])} > {len(lector.fieldnames)})"
            )
        valores = {}
        for columna in COLUMNAS_NUMERICAS:
            numero, error = _convertir_numero((fila.get(columna) or "").strip(), columna, linea)
            if error:
                errores_fila.append(error)
            valores[columna] = numero
        if errores_fila:
            errores.extend(errores_fila)
            continue
        evento = (fila.get("evento") or "").strip()
        muestras.append(MuestraECG(evento=evento, **valores))
        ubicaciones.append(f"muestra {len(muestras)}, línea {linea}")

    return _crear_senal(muestras, origen, ubicaciones, errores)


def leer_csv_ecg(ruta: str | Path | None) -> SenalECG:
    """Lee un archivo CSV de ECG desde disco y devuelve la señal validada."""
    if ruta is None or str(ruta) == "":
        raise ErrorSenalECG("sin archivo", ["No se seleccionó ningún archivo"])
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ErrorSenalECG(ruta.name, [f"no existe el archivo '{ruta}'"])
    texto = ruta.read_text(encoding="utf-8-sig")
    return interpretar_csv_ecg(texto, ruta.name)
