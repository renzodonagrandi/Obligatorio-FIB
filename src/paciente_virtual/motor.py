from collections import Counter
from dataclasses import dataclass

from .agentes import Agente
from .estado import EstadoFisiologicoGlobal, ValorFisiologico


@dataclass(frozen=True)
class DefinicionVariable:
    unidad: str
    minimo: float
    maximo: float


@dataclass(frozen=True)
class EventoPerturbacion:
    nombre: str
    tiempo_s: float
    cambios: dict[str, float]
    duracion_s: float = 0.0


class MotorSimulacion:
    def __init__(self, estado, agentes: list[Agente], catalogo, paso_s: float = 0.1,
                 eventos: list[EventoPerturbacion] | None = None):
        if paso_s <= 0:
            raise ValueError("El paso temporal debe ser positivo")
        self.estado: EstadoFisiologicoGlobal = estado
        self.agentes = list(agentes)
        self.catalogo: dict[str, DefinicionVariable] = dict(catalogo)
        self.paso_s = paso_s
        self.historial: list[dict[str, float]] = []
        self.eventos = sorted(eventos or [], key=lambda evento: evento.tiempo_s)
        self.eventos_aplicados: list[dict] = []
        self._indices_eventos_aplicados: set[int] = set()
        self._inicios_rampa: dict[int, dict[str, float]] = {}
        self._validar_arquitectura()
        self._guardar_fila()

    def _validar_arquitectura(self) -> None:
        disponibles = set(self.estado.instantanea().variables)
        salidas = [salida for agente in self.agentes for salida in agente.salidas]
        duplicadas = [nombre for nombre, cantidad in Counter(salidas).items() if cantidad > 1]
        if duplicadas:
            raise ValueError(f"Variables con mas de un productor: {duplicadas}")
        declaradas = disponibles | set(salidas)
        faltantes = {entrada for agente in self.agentes for entrada in agente.entradas if entrada not in declaradas}
        if faltantes:
            raise ValueError(f"Entradas sin valor inicial ni productor: {sorted(faltantes)}")
        no_catalogadas = declaradas - set(self.catalogo)
        if no_catalogadas:
            raise ValueError(f"Variables ausentes del catalogo: {sorted(no_catalogadas)}")

    def ejecutar_ciclo(self) -> None:
        self._aplicar_eventos_pendientes()
        instantanea = self.estado.instantanea()
        propuestas = {}
        for agente in self.agentes:
            for publicacion in agente.calcular(instantanea, self.paso_s):
                definicion = self.catalogo[publicacion.variable]
                if publicacion.unidad != definicion.unidad:
                    raise ValueError(f"Unidad incorrecta para {publicacion.variable}")
                if not definicion.minimo <= publicacion.valor <= definicion.maximo:
                    raise ValueError(f"Valor fuera del dominio para {publicacion.variable}: {publicacion.valor}")
                propuestas[publicacion.variable] = ValorFisiologico(
                    publicacion.valor, publicacion.unidad, publicacion.calidad, agente.identificador
                )
        self.estado.confirmar(propuestas, self.paso_s)
        self._guardar_fila()

    def _aplicar_eventos_pendientes(self) -> None:
        for indice, evento in enumerate(self.eventos):
            if indice in self._indices_eventos_aplicados or evento.tiempo_s > self.estado.tiempo_s + 1e-9:
                continue
            if evento.duracion_s < 0:
                raise ValueError(f"Evento {evento.nombre}: la duracion no puede ser negativa")
            es_nuevo = indice not in self._inicios_rampa
            if es_nuevo:
                instantanea = self.estado.instantanea()
                self._inicios_rampa[indice] = {
                    nombre: instantanea.obtener(nombre) for nombre in evento.cambios
                }
            cambios = {}
            for nombre, valor in evento.cambios.items():
                if nombre not in self.catalogo:
                    raise ValueError(f"Evento {evento.nombre}: variable desconocida {nombre}")
                definicion = self.catalogo[nombre]
                if not definicion.minimo <= valor <= definicion.maximo:
                    raise ValueError(f"Evento {evento.nombre}: {nombre} fuera del dominio")
                if evento.duracion_s > 0:
                    fraccion = min(1.0, (self.estado.tiempo_s - evento.tiempo_s) / evento.duracion_s)
                    inicial = self._inicios_rampa[indice][nombre]
                    valor = inicial + fraccion * (valor - inicial)
                cambios[nombre] = ValorFisiologico(
                    valor, definicion.unidad, productor=f"evento:{evento.nombre}"
                )
            self.estado.aplicar_evento(cambios)
            finalizado = evento.duracion_s == 0 or self.estado.tiempo_s >= evento.tiempo_s + evento.duracion_s - 1e-9
            if finalizado:
                self._indices_eventos_aplicados.add(indice)
            if es_nuevo:
                self.eventos_aplicados.append({
                    "nombre": evento.nombre,
                    "tiempo_s": self.estado.tiempo_s,
                    "duracion_s": evento.duracion_s,
                    "cambios": dict(evento.cambios),
                })

    def ejecutar(self, duracion_s: float) -> list[dict[str, float]]:
        ciclos = round(duracion_s / self.paso_s)
        for _ in range(ciclos):
            self.ejecutar_ciclo()
        return list(self.historial)

    def _guardar_fila(self) -> None:
        instantanea = self.estado.instantanea()
        fila = {"ciclo": instantanea.ciclo, "tiempo_s": instantanea.tiempo_s}
        fila.update({nombre: dato.valor for nombre, dato in instantanea.variables.items()})
        self.historial.append(fila)
