# Contexto del código base — Paciente Virtual (obligatorio ECG)

> Documento generado leyendo **todos** los archivos `.py` del proyecto, `README.md`,
> `CONTRATO_ECG.md` y `pyproject.toml`, y ejecutando comandos de inspección
> (fecha: 2026-10-11). No se modificó ningún archivo existente.
> Las referencias son `archivo:línea` (números aproximados pero verificados).
> Lo que no queda claro en el código está marcado como **⚠️ A confirmar**.

---

## 1. Resumen general

- **Qué es:** prototipo educativo de "Paciente Virtual" formado por agentes
  computacionales (cardiovascular, respiratorio, nervioso) que intercambian variables
  fisiológicas a través de un estado global, orquestados por un motor de paso fijo.
  `README.md:3-5`: *"no representa todavía un modelo fisiológico validado"*.
- **Paquete:** `src/paciente_virtual/` (layout `src`). No hace falta instalarlo: cada script
  de la raíz y el archivo de pruebas agregan `src` a `sys.path` a mano
  (`ejecutar_simulacion.py:7-14`, `ejecutar_escenarios.py:5-6`, `interfaz_web.py:9-10`,
  `pruebas/test_paciente_virtual.py:5`).
- **`pyproject.toml`:** `name = "paciente-virtual"`, `version = "0.1.0"`,
  `requires-python = ">=3.10"` (línea 9). **No hay dependencias externas**: solo usa la
  biblioteca estándar (`dataclasses`, `csv`, `json`, `http.server`, `math`, `argparse`, etc.).
  Build backend: setuptools ≥ 68. Tiene configuración de pytest (`pythonpath = ["src"]`,
  `testpaths = ["pruebas"]`), pero el curso usa `unittest`.

### ⚠️ Versión de Python: trampa real en esta máquina

- El código **exige Python ≥ 3.10**: usa la sintaxis `X | None` en anotaciones que se
  evalúan en tiempo de definición (p. ej. `motor.py:25`
  `eventos: list[EventoPerturbacion] | None = None`, `configuracion.py:34`,
  `modelos.py:30/90/169`). (`:=` en `analisis.py:37` solo exige 3.8.)
- En esta máquina `python3` apunta a **pyenv 3.9.18** (variable de entorno `PYENV_VERSION`).
  Con esa versión **todo lo que importa `paciente_virtual` falla al importar**
  (`interfaz_web.py`, `ejecutar_simulacion.py`, `ejecutar_escenarios.py` y las pruebas):
  `TypeError: unsupported operand type(s) for |: 'types.GenericAlias' and 'NoneType'`.
  `agente_externo_ecg.py` **sí funciona en 3.9** (no importa el paquete; verificado: genera un CSV
  idéntico). Ojo: los comandos de entrega son literalmente `python3 agente_externo_ecg.py` y
  `python3 interfaz_web.py`.
- Con `/usr/bin/python3.12` (3.12.3) funciona todo y pasan las 25 pruebas.
- Para el código nuevo se puede usar sintaxis de 3.10+ (el código base ya la usa). Para
  ejecutar hace falta 3.10+ (p. ej. `PYENV_VERSION=system python3 ...` o
  `python3.12 ...`). Ver §9.

### Scripts de la raíz

| Script | Cómo se ejecuta | Qué hace |
|---|---|---|
| `agente_externo_ecg.py` | `python3 agente_externo_ecg.py [--salida RUTA] [--duracion 20] [--frecuencia-cardiaca 70] [--inicio-arritmia 5] [--fin-arritmia 14]` | Es la "fuente externa". Genera un ECG sintético a 250 Hz con una taquiarritmia y lo escribe como CSV (por defecto `resultados/ecg_simulado.csv`). **No** importa nada del paquete. Detalle en §7. |
| `ejecutar_simulacion.py` | `python3 ejecutar_simulacion.py` | Crea el motor de referencia con `paso_s=0.1` y `valores_iniciales={"presion_arterial_co2": 55.0}` (**no es basal**: arranca con CO2 alto para probar la propagación nervioso→respiratorio), simula 30 s, escribe `resultados/simulacion.csv` e imprime FC, PAM y PaCO2 finales (`ejecutar_simulacion.py:19-38`). |
| `ejecutar_escenarios.py` | `python3 ejecutar_escenarios.py` | Recorre `ESCENARIOS` (basal, hemorragia, aumento_resistencia, hipoventilacion), ejecuta cada uno con su `duracion_s`, guarda `resultados/<nombre>.csv` e imprime FC/PAM/PaCO2 finales (`ejecutar_escenarios.py:21-31`). |
| `interfaz_web.py` | `python3 interfaz_web.py` | Servidor HTTP local (`ThreadingHTTPServer`) en `http://127.0.0.1:8765` con una página HTML/JS embebida. Abre el navegador a los 0,7 s. Detalle en §8. |

---

## 2. Árbol de archivos

```
paciente_virtual_estudiantes_arritmia/
├── agente_externo_ecg.py        # Fuente externa: genera el CSV de ECG con taquiarritmia (no usa el paquete)
├── ejecutar_simulacion.py       # Corre 30 s con PaCO2 inicial = 55 y guarda resultados/simulacion.csv
├── ejecutar_escenarios.py       # Corre todos los ESCENARIOS y guarda un CSV por escenario
├── interfaz_web.py              # Servidor HTTP + HTML/JS embebido (gráficas canvas); endpoints /, /simular, /sensibilidad
├── README.md                    # Descripción general, comandos y resumen de los modelos
├── CONTRATO_ECG.md              # Contrato de la tarea ECG (formato CSV, variables, salida mínima, informe)
├── ENUNCIADO_OBLIGATORIO_ECG.md # Letra del obligatorio
├── pyproject.toml               # Metadatos; requires-python >= 3.10; sin dependencias
├── resultados/
│   └── ecg_simulado.csv         # CSV de ECG ya generado (5001 filas, 20 s, 250 Hz) — idéntico a regenerarlo con valores por defecto
├── pruebas/
│   ├── __init__.py              # Solo docstring: """Pruebas automáticas del Paciente Virtual."""
│   └── test_paciente_virtual.py # 25 pruebas unittest del sistema base
└── src/paciente_virtual/
    ├── __init__.py              # Exporta CalidadDato, EstadoFisiologicoGlobal, ValorFisiologico, MotorSimulacion
    ├── agentes.py               # Publicacion (dataclass), Agente (Protocol), acercar() (primer orden)
    ├── estado.py                # CalidadDato (Enum), ValorFisiologico, InstantaneaEstado, EstadoFisiologicoGlobal
    ├── motor.py                 # DefinicionVariable, EventoPerturbacion, MotorSimulacion
    ├── modelos.py               # AgenteNervioso, AgenteCardiovascular, AgenteRespiratorio + Parametros*, limitar()
    ├── configuracion.py         # CATALOGO de variables y crear_motor_referencia() (← aquí se registra la lista de agentes)
    ├── escenarios.py            # Escenario (dataclass), ESCENARIOS, obtener_escenario()
    └── analisis.py              # VARIABLES_CLAVE, analizar_historial() (métricas + resumen en texto)
```

(No hay repositorio git. Hay carpetas `__pycache__` generadas por ejecuciones previas.)

---

## 3. Arquitectura de agentes

### 3.1 Tipos compartidos (textuales)

`src/paciente_virtual/agentes.py:7-26`

```python
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
```

`src/paciente_virtual/estado.py:7-35`

```python
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
        # KeyError("Variable requerida ausente: ...") si no existe
        # ValueError("Variable no disponible: ...") si calidad == NO_DISPONIBLE
        ...
```

Cosas a notar:

- `Agente` es un `typing.Protocol` (tipado estructural): **no hay clase base**. Un agente
  es cualquier objeto con los atributos `identificador`, `entradas`, `salidas` y el método
  `calcular(estado, paso_s) -> list[Publicacion]`. Los agentes existentes los definen como
  **atributos de clase** (`modelos.py:26-28`, `79-88`, `161-167`).
- El motor **solo llama `calcular`** (`motor.py:59`). `entradas` y `salidas` se usan
  únicamente en la validación de arquitectura al construir el motor (`motor.py:40-52`).
  El motor **no comprueba** que un agente publique solo variables de sus `salidas`
  ni que publique todas. ⚠️ A confirmar si eso es intencional (parece que sí: es un prototipo).
- `CalidadDato` **no** tiene un valor `incorrecto`. El contrato pide los estados de calidad de la
  señal `valido`, `degradado` o `incorrecto` (`CONTRATO_ECG.md:41`): `valido` y `degradado`
  coinciden con `CalidadDato.VALIDO` / `CalidadDato.DEGRADADO`, pero `incorrecto` no existe en el
  enum. ⚠️ A confirmar si la calidad de la señal ECG debe reutilizar `CalidadDato` o ser un
  tipo propio del lector (ninguna de las dos cosas está en el código).
- `InstantaneaEstado.variables` es un `MappingProxyType` (solo lectura,
  `estado.py:47`); escribir en ella lanza `TypeError` (lo verifica una prueba).
- `acercar` es la dinámica de primer orden usada en todos los modelos:
  `x_{k+1} = x_k + min(1, rapidez·dt)·(objetivo − x_k)`, con `rapidez = 1/τ`.

### 3.2 Agentes existentes (`src/paciente_virtual/modelos.py`)

#### `AgenteNervioso` (`modelos.py:25-63`), `identificador = "nervioso"`

- **Entradas declaradas:** `presion_arterial_media`, `presion_arterial_co2`, `presion_arterial_o2`.
  Además lee sus propias salidas anteriores (`actividad_simpatica`, `actividad_parasimpatica`,
  `impulso_respiratorio`) con `estado.obtener`, sin declararlas como entradas.
- **Salidas:** `actividad_simpatica` (`"1"`), `actividad_parasimpatica` (`"1"`), `impulso_respiratorio` (`"1"`).
- **Rol:** barorreflejo + quimiorreflejo reducidos. Parámetros en `ParametrosNerviosos`
  (`modelos.py:10-22`): `presion_referencia_mmhg=90.2`, `co2_referencia_mmhg=40.0`,
  `umbral_hipoxia_mmhg=80.0`, `ganancia_barorreflejo_simpatica=1/20`,
  `ganancia_barorreflejo_parasimpatica=0.8/20`, `ganancia_co2_respiratoria=0.06`,
  `ganancia_hipoxia_respiratoria=0.015`, `ganancia_quimica_simpatica=0.25`,
  τ simpática 4 s, τ parasimpática 1 s, τ respiratoria 2 s.
- **Ecuaciones** (`modelos.py:42-58`):
  ```
  error_presion   = 90.2 − PAM
  exceso_co2      = PaCO2 − 40
  deficit_o2      = max(0, 80 − PaO2)
  estimulo_quimico = max(0, 0.06·exceso_co2) + 0.015·deficit_o2
  obj_simp  = limitar(1 + (1/20)·error_presion + 0.25·estimulo_quimico, 0, 3)
  obj_para  = limitar(1 − (0.8/20)·error_presion, 0, 2)
  obj_imp   = limitar(1 + 0.06·exceso_co2 + 0.015·deficit_o2, 0.2, 3)
  cada una → acercar(actual, objetivo, 1/τ, dt)
  ```

#### `AgenteCardiovascular` (`modelos.py:78-141`), `identificador = "cardiovascular"`

- **Entradas declaradas** (`modelos.py:80-84`): `actividad_simpatica`, `actividad_parasimpatica`,
  `saturacion_arterial_o2`, `volumen_sanguineo`, `contractilidad`,
  `resistencia_vascular_sistemica`, `contenido_arterial_o2`,
  **`frecuencia_cardiaca_objetivo`**, **`eficiencia_ritmo`**. También lee sus salidas previas
  `frecuencia_cardiaca` y `presion_arterial_media`.
- **Salidas:** `frecuencia_cardiaca` (`latido/min`), `volumen_sistolico` (`mL/latido`),
  `gasto_cardiaco` (`L/min`), `aporte_sistemico_o2` (`mL/min`), `presion_arterial_media` (`mmHg`).
- **Rol:** modelo concentrado de FC, VS, GC, PAM y DO2. Ecuaciones en §5.

#### `AgenteRespiratorio` (`modelos.py:160-216`), `identificador = "respiratorio"`

- **Entradas declaradas:** `impulso_respiratorio`, `factor_ventilatorio`, `hemoglobina`, `bicarbonato`
  (además lee sus propios `frecuencia_respiratoria` y `presion_arterial_co2` anteriores).
- **Salidas:** `frecuencia_respiratoria` (`respiracion/min`), `ventilacion_minuto` (`L/min`),
  `ventilacion_alveolar` (`L/min`), `presion_arterial_co2` (`mmHg`), `presion_arterial_o2` (`mmHg`),
  `saturacion_arterial_o2` (`%`), `contenido_arterial_o2` (`mL/dL`), `ph_arterial` (`"1"`).
- **Rol:** ventilación, PaCO2 dinámica (τ = 12 s), PAO2 por la ecuación alveolar simplificada,
  SaO2 por la curva de Hill (P50 = 26,8, n = 2,7), CaO2 = 1,34·Hb·SaO2 + 0,003·PaO2, pH por
  Henderson-Hasselbalch. Lanza `ValueError` si el volumen corriente ≤ espacio muerto (`modelos.py:171-172`).

No hay otros agentes. `limitar(valor, minimo, maximo)` está en `modelos.py:219-220`.

### 3.3 Tabla completa de variables del sistema

Fuente: `CATALOGO` (`configuracion.py:6-31`) y valores iniciales (`configuracion.py:36-61`).
"Consume" = la lee con `estado.obtener` (D = declarada en `entradas`; P = lee su propio valor previo sin declararlo).

| Variable | Unidad (exacta) | Dominio [min, max] | Inicial | Publica | Consume |
|---|---|---|---|---|---|
| `frecuencia_cardiaca` | `latido/min` | 0 – 300 | 70.0 | cardiovascular | cardiovascular (P) |
| `volumen_sistolico` | `mL/latido` | 0 – 250 | 70.0 | cardiovascular | — |
| `gasto_cardiaco` | `L/min` | 0 – 30 | 4.9 | cardiovascular | — |
| `aporte_sistemico_o2` | `mL/min` | 0 – 5000 | 970.0 | cardiovascular | — |
| `presion_arterial_media` | `mmHg` | 0 – 250 | 90.2 | cardiovascular | nervioso (D), cardiovascular (P) |
| `volumen_sanguineo` | `L` | 1 – 10 | 5.0 | nadie (condición inicial / evento / interfaz) | cardiovascular (D) |
| `contractilidad` | `1` | 0.1 – 3 | 1.0 | nadie (cond. inicial / evento / interfaz) | cardiovascular (D) |
| **`frecuencia_cardiaca_objetivo`** | **`latido/min`** | **0 – 240** | **0.0** | **nadie (hoy)** → lo deberá publicar `AgenteECG` | cardiovascular (D) |
| **`eficiencia_ritmo`** | **`1`** | **0.2 – 1.2** | **1.0** | **nadie (hoy)** → lo deberá publicar `AgenteECG` | cardiovascular (D) |
| `resistencia_vascular_sistemica` | `mmHg min/L` | 1 – 50 | 18.0 | nadie (cond. inicial / evento / interfaz) | cardiovascular (D) |
| `frecuencia_respiratoria` | `respiracion/min` | 0 – 100 | 12.0 | respiratorio | respiratorio (P) |
| `factor_ventilatorio` | `1` | 0.1 – 3 | 1.0 | nadie (cond. inicial / evento / interfaz) | respiratorio (D) |
| `hemoglobina` | `g/dL` | 3 – 25 | 15.0 | nadie (cond. inicial / interfaz) | respiratorio (D) |
| `bicarbonato` | `mmol/L` | 3 – 50 | 24.0 | nadie (cond. inicial / interfaz) | respiratorio (D) |
| `ventilacion_minuto` | `L/min` | 0 – 40 | 6.0 | respiratorio | — |
| `ventilacion_alveolar` | `L/min` | 0 – 35 | 4.32 | respiratorio | — |
| `presion_arterial_co2` | `mmHg` | 0 – 200 | 40.0 | respiratorio | nervioso (D), respiratorio (P) |
| `presion_arterial_o2` | `mmHg` | 0 – 700 | 90.0 | respiratorio | nervioso (D) |
| `saturacion_arterial_o2` | `%` | 0 – 100 | 97.0 | respiratorio | cardiovascular (D) |
| `contenido_arterial_o2` | `mL/dL` | 0 – 35 | 19.8 | respiratorio | cardiovascular (D) |
| `ph_arterial` | `1` | 6.5 – 8 | 7.40 | respiratorio | — |
| `actividad_simpatica` | `1` | 0 – 3 | 1.0 | nervioso | cardiovascular (D), nervioso (P) |
| `actividad_parasimpatica` | `1` | 0 – 2 | 1.0 | nervioso | cardiovascular (D), nervioso (P) |
| `impulso_respiratorio` | `1` | 0 – 3 | 1.0 | nervioso | respiratorio (D), nervioso (P) |

Notas:
- Las unidades adimensionales son el string **`"1"`**, no `""` ni `None`.
- `mmHg min/L` lleva un **espacio** (no `·`).
- `frecuencia_cardiaca_objetivo` y `eficiencia_ritmo` **ya están** en `CATALOGO` y en los
  valores iniciales, así que el `AgenteECG` no necesita tocar `configuracion.py` para declararlas;
  solo hay que agregarlo a la lista de agentes.

---

## 4. Motor de simulación (`src/paciente_virtual/motor.py`)

### 4.1 Tipos

```python
@dataclass(frozen=True)
class DefinicionVariable:      # motor.py:8-12
    unidad: str
    minimo: float
    maximo: float

@dataclass(frozen=True)
class EventoPerturbacion:      # motor.py:15-20
    nombre: str
    tiempo_s: float
    cambios: dict[str, float]
    duracion_s: float = 0.0    # > 0 → rampa lineal
```

### 4.2 Construcción y punto de registro de agentes

```python
class MotorSimulacion:   # motor.py:23-25
    def __init__(self, estado, agentes: list[Agente], catalogo, paso_s: float = 0.1,
                 eventos: list[EventoPerturbacion] | None = None):
```

El motor **no** arma la lista de agentes: la recibe. La lista se arma en
**`crear_motor_referencia`** (`configuracion.py:34-68`):

```python
def crear_motor_referencia(paso_s: float = 0.1, valores_iniciales: dict[str, float] | None = None,
                           eventos: list[EventoPerturbacion] | None = None) -> MotorSimulacion:
    iniciales = { ... }                       # configuracion.py:36-61
    ...                                        # valores_iniciales solo puede sobrescribir nombres existentes (KeyError si no)
    agentes = [AgenteNervioso(), AgenteCardiovascular(), AgenteRespiratorio()]   # configuracion.py:67  ◀◀◀ PUNTO DE REGISTRO
    return MotorSimulacion(EstadoFisiologicoGlobal(iniciales), agentes, CATALOGO, paso_s, eventos)
```

> 📌 **Aquí hay que registrar el `AgenteECG`** (`configuracion.py:67`), o bien construir un
> `MotorSimulacion` con una lista que lo incluya. Hoy `crear_motor_referencia` **no tiene
> ningún parámetro para agregar agentes**. Lo usan `ejecutar_simulacion.py:22`,
> `Escenario.crear_motor` (`escenarios.py:14-15`), `interfaz_web.py:60` y todas las pruebas.
> Si se cambia su firma, conviene que el parámetro nuevo sea opcional para que las 25
> pruebas sigan pasando. ⚠️ A confirmar el diseño (parámetro opcional, función nueva o
> construir el motor a mano en la interfaz).

### 4.3 Paso, duración y bucle

- `paso_s` por defecto es **0.1 s** (motor, `crear_motor_referencia`, `Escenario.crear_motor`,
  interfaz). `paso_s <= 0` lanza `ValueError` (`motor.py:26-27`). La interfaz acepta (0, 1] s
  (`interfaz_web.py:57-59`).
- El motor no tiene duración por defecto: `ejecutar(duracion_s)` corre
  `round(duracion_s / paso_s)` ciclos (`motor.py:109-113`) y devuelve una copia del historial.
  Duraciones: basal 60 s, hemorragia 90 s, aumento_resistencia 60 s, hipoventilacion 90 s;
  `ejecutar_simulacion.py` 30 s; interfaz: campo `duracion_s` = 60 por defecto, rango 1–600.
- **Un ciclo** (`ejecutar_ciclo`, `motor.py:54-69`):
  1. `_aplicar_eventos_pendientes()`: aplica eventos cuyo `tiempo_s <= estado.tiempo_s + 1e-9`
     **directamente sobre el estado y sin avanzar el reloj** (`estado.aplicar_evento`).
  2. `instantanea = self.estado.instantanea()`: una **única** foto inmutable del estado.
  3. Para cada agente en orden de lista: `agente.calcular(instantanea, self.paso_s)`. Cada
     `Publicacion` se valida (unidad exacta y dominio) y se guarda en `propuestas[variable]`
     como `ValorFisiologico(valor, unidad, calidad, agente.identificador)`.
  4. `estado.confirmar(propuestas, paso_s)`: aplica **todas** las propuestas juntas, `ciclo += 1`,
     `tiempo_s = round(tiempo_s + paso_s, 12)` (`estado.py:50-55`).
  5. `_guardar_fila()`.

### 4.4 Orden y dependencias (semántica importante)

- **Todos los agentes leen la misma instantánea** (esquema tipo Jacobi). Por eso el orden de la
  lista (`nervioso, cardiovascular, respiratorio`) **no altera el flujo de datos**: un agente
  nunca ve lo que otro publicó en el mismo ciclo. Y como el motor prohíbe dos productores de
  la misma variable (`motor.py:42-45`), tampoco hay sobrescrituras dependientes del orden.
- **Retardo de un ciclo:** lo que publica un agente en el ciclo con instantánea `t` queda
  confirmado en `t+dt`, y sus consumidores lo usan recién en el ciclo siguiente. Para el
  `AgenteECG`: si en la instantánea `t = 5.0` publica la FC de la arritmia, la fila del
  historial `t = 5.1` ya muestra `frecuencia_cardiaca_objetivo` cambiada, pero
  `frecuencia_cardiaca`/`volumen_sistolico` cambian recién en la fila `t = 5.2`.
- **Los eventos no tienen ese retardo:** se aplican antes de tomar la instantánea, así que el
  cardiovascular los ve en el mismo ciclo (comprobado: con un evento a `t=5.0`, `volumen_sistolico`
  ya cambia en la fila `t=5.1`).
- **Persistencia:** `confirmar` hace `siguiente = dict(anterior); siguiente.update(propuestas)`.
  Si un agente deja de publicar una variable, **se conserva el último valor confirmado**. Esto
  define qué pasa si el `AgenteECG` no publica nada cuando se terminan las muestras.

### 4.5 Entradas no publicadas / validaciones

`_validar_arquitectura` (`motor.py:40-52`, se ejecuta en el constructor):
1. **Productores duplicados:** si dos agentes declaran la misma salida →
   `ValueError("Variables con mas de un productor: [...]")`.
2. **Entradas sin origen:** toda entrada declarada debe tener valor inicial **o** productor →
   `ValueError("Entradas sin valor inicial ni productor: [...]")`.
3. **Catálogo:** toda variable inicial o producida debe estar en `CATALOGO` →
   `ValueError("Variables ausentes del catalogo: [...]")`.

En cada ciclo (`motor.py:60-64`):
- `publicacion.unidad != definicion.unidad` → `ValueError("Unidad incorrecta para <var>")` (comparación de strings exacta).
- Fuera de `[minimo, maximo]` → `ValueError("Valor fuera del dominio para <var>: <valor>")`.
- Una publicación de una variable que no está en el catálogo → `KeyError` (por `self.catalogo[...]`).

Si una entrada **no** se publica nunca pero tiene valor inicial, se usa el valor inicial
indefinidamente. Así funcionan hoy `frecuencia_cardiaca_objetivo = 0.0` y `eficiencia_ritmo = 1.0`.
`InstantaneaEstado.obtener` lanza `KeyError` si el nombre no existe, o `ValueError` si la calidad es
`NO_DISPONIBLE` (`estado.py:28-35`).

Eventos (`motor.py:71-107`): validan que la variable esté en el catálogo y en dominio. Con
`duracion_s > 0` interpolan linealmente desde el valor que había al inicio. Una duración negativa
lanza `ValueError` en el primer ciclo. Cada evento nuevo agrega a `motor.eventos_aplicados` un
dict `{"nombre", "tiempo_s", "duracion_s", "cambios"}`.

### 4.6 Estado e historial

- `EstadoFisiologicoGlobal` (`estado.py:38-61`): guarda `_variables` (dict nombre →
  `ValorFisiologico`), `ciclo` y **`tiempo_s`** (float, empieza en 0.0, redondeado a 12 decimales).
  Métodos: `instantanea()`, `confirmar(publicaciones, paso_s)`, `aplicar_evento(cambios)`.
- En `calcular`, el agente recibe `estado` = `InstantaneaEstado`, con `estado.tiempo_s`
  = tiempo **al inicio** del ciclo (0.0, 0.1, 0.2, …) y `estado.ciclo`.
- ⚠️ **Trampa de flotantes:** `tiempo_s` del motor se acumula sumando `0.1` y redondeando a 12
  decimales; los tiempos del CSV tienen hasta 6 decimales (`0.004`, `4.996`, …). No conviene
  buscar coincidencia exacta: hay que usar una búsqueda con tolerancia (anterior / más cercana /
  `bisect`).
- `motor.historial`: `list[dict[str, float]]`. Cada fila es
  `{"ciclo", "tiempo_s", <todas las variables del estado>: valor}` (`motor.py:115-119`). La fila 0
  (condición inicial, t=0) se guarda en el constructor, así que `ejecutar(60)` con dt 0,1 devuelve
  **601 filas**. El historial **solo guarda valores**, no unidades, calidad ni productor.

---

## 5. Modelo cardiovascular en detalle (`modelos.py:66-141`)

Parámetros (`ParametrosCardiovasculares`, `modelos.py:66-75`):
`frecuencia_basal_lpm=70.0`, `volumen_sistolico_basal_ml=70.0`,
`volumen_sanguineo_referencia_l=5.0`, `resistencia_referencia_mmhg_min_l=18.0`,
`presion_venosa_central_mmhg=2.0`, `ganancia_simpatica_frecuencia=25.0`,
`constante_tiempo_frecuencia_s=3.0`, `constante_tiempo_presion_s=2.0`.

Ecuaciones textuales (`modelos.py:107-134`):

```python
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
```

donde `frecuencia_externa = estado.obtener("frecuencia_cardiaca_objetivo")` y
`eficiencia_ritmo = estado.obtener("eficiencia_ritmo")` (`modelos.py:102-103`).

### Uso de las entradas del ECG

- **`frecuencia_cardiaca_objetivo`**: **0.0 actúa como "sin fuente externa"** (valor inicial,
  `configuracion.py:44`). Si es `> 0`, **reemplaza por completo** el objetivo de FC calculado por
  el sistema nervioso (simpático/parasimpático/hipoxia), limitado a [30, 220]. La FC real sigue
  ese objetivo con primer orden, **τ = 3 s** (`acercar` con rapidez 1/3: con dt = 0,1 avanza 3,33 %
  de la diferencia por ciclo). El catálogo admite 0 – 240.
- **`eficiencia_ritmo`**: multiplica directamente el `volumen_sistolico`, **sin constante de tiempo**:
  el efecto es **instantáneo** en el ciclo en que el cardiovascular lo lee. Valor por defecto 1.0;
  catálogo 0.2 – 1.2; VS limitado a [10, 180].
- **⚠️ Decisión de diseño (no es un hecho del CSV):** en las filas `ritmo_basal` el CSV trae
  `frecuencia_cardiaca_lpm = 70.0`. Si el agente publica 70 en esos tramos, la FC queda
  **fijada en 70 e ignora el barorreflejo**, también en la recuperación. Si en cambio publica 0
  (o deja de publicar >0), le devuelve el control al sistema nervioso. Las dos opciones dan
  recuperaciones distintas (ver la emulación de §10). El enunciado pide mapear
  `frecuencia_cardiaca_lpm → frecuencia_cardiaca_objetivo`, lo que sugiere publicar 70. ⚠️ A confirmar
  con el docente o justificar en el informe.

### Variables publicadas (nombres exactos)

| Magnitud | Variable | Unidad | Dinámica |
|---|---|---|---|
| Frecuencia cardíaca | `frecuencia_cardiaca` | `latido/min` | primer orden, τ = 3 s |
| Volumen sistólico | `volumen_sistolico` | `mL/latido` | algebraica (instantánea) |
| Gasto cardíaco | `gasto_cardiaco` | `L/min` | algebraica: FC·VS/1000 |
| Aporte sistémico de O2 | `aporte_sistemico_o2` | `mL/min` | algebraica: GC·CaO2·10 |
| Presión arterial media | `presion_arterial_media` | `mmHg` | primer orden hacia PVC + GC·RVS, τ = 2 s |

### Interacción con el agente nervioso (afecta la recuperación)

- Una caída de PAM (`error_presion > 0`) sube el simpático (τ = 4 s) y baja el parasimpático
  (τ = 1 s). Una subida de PAM hace lo contrario.
- El simpático actúa sobre el cardiovascular por dos vías: (a) el objetivo de FC
  (+25·(simp−1) −15·(para−1)), **solo cuando `frecuencia_cardiaca_objetivo` ≤ 0**; y (b) la
  contractilidad efectiva (×(1 + 0,25·(simp−1))), **siempre**, aunque haya FC externa.
- Durante la arritmia la PAM cae (VS × 0,45), el simpático sube y eso **aumenta algo el VS**
  por la contractilidad. Al terminar, la eficiencia vuelve a 1 de golpe con simpático todavía
  elevado y FC todavía alta (τ = 3 s): **rebote** de GC, DO2 y PAM, y después el barorreflejo frena
  (simpático < 1, parasimpático > 1). Ver números en §10.
- Hay un acoplamiento débil adicional: `estimulo_hipoxia` (SaO2 < 95) y `contenido_arterial_o2`
  vienen del respiratorio, pero en estos escenarios casi no cambian.

---

## 6. Configuración, escenarios y análisis

### `configuracion.py`
- `CATALOGO` (líneas 6-31): ver la tabla de §3.3.
- `crear_motor_referencia(paso_s=0.1, valores_iniciales=None, eventos=None)` (líneas 34-68):
  valores iniciales fijos (36-61). `valores_iniciales` permite sobrescribir solo nombres
  existentes (KeyError si el nombre es desconocido) y conserva la unidad original. Lista de
  agentes en la línea 67.
- Basales: FC 70, VS 70, GC 4,9, DO2 970 (inicial), PAM 90,2, Vsang 5,0, contractilidad 1,0,
  RVS 18, FR 12, Hb 15, HCO3 24, PaCO2 40, PaO2 90, SaO2 97, CaO2 19,8, pH 7,40, simp/para/impulso 1,0.

### `escenarios.py`
```python
@dataclass(frozen=True)
class Escenario:                      # escenarios.py:7-15
    identificador: str
    descripcion: str
    duracion_s: float
    eventos: tuple[EventoPerturbacion, ...] = ()
    def crear_motor(self, paso_s: float = 0.1) -> MotorSimulacion:
        return crear_motor_referencia(paso_s=paso_s, eventos=list(self.eventos))
```
`ESCENARIOS` (líneas 18-38):

| Clave | Duración | Evento |
|---|---|---|
| `basal` | 60 s | ninguno |
| `hemorragia` | 90 s | `perdida_volumen` a 10 s: `volumen_sanguineo` = 4.0 |
| `aumento_resistencia` | 60 s | `vasoconstriccion` a 10 s: `resistencia_vascular_sistemica` = 24.0 |
| `hipoventilacion` | 90 s | `depresion_respiratoria` a 10 s: `factor_ventilatorio` = 0.5 |

`obtener_escenario(identificador)` lanza `KeyError("Escenario desconocido: ...")`. La interfaz
no la usa: accede directo a `ESCENARIOS[nombre]`.

### `analisis.py`
- `VARIABLES_CLAVE` (líneas 3-6): `frecuencia_cardiaca`, `presion_arterial_media`, `gasto_cardiaco`,
  `presion_arterial_co2`, `presion_arterial_o2`, `saturacion_arterial_o2`, `ph_arterial`,
  `actividad_simpatica`, `actividad_parasimpatica`, `aporte_sistemico_o2`.
  **No incluye `volumen_sistolico`.**
- `analizar_historial(historial, eventos) -> {"metricas": {...}, "resumen": [str, ...]}` (líneas 9-32):
  la referencia "basal" es la fila más cercana al **primer evento**; si no hay eventos, es la
  **primera fila**. Por variable devuelve `basal`, `minimo`, `tiempo_minimo_s`, `maximo`,
  `tiempo_maximo_s`, `final`, `cambio_final_porcentaje`, `recuperacion_porcentaje`. **Sin eventos,
  `recuperacion_porcentaje` = 100** siempre.
- `_crear_resumen` (líneas 35-47): sin eventos → `"Ejecución basal sin perturbaciones."`; con eventos,
  frases según umbrales (PAM −5 %, simpático +5 %, PaCO2 +3, pH −0,03, DO2 −10 %). El texto usa
  tildes, p. ej. `"Apareció activación simpática compensatoria dentro del modelo."`.
- ⚠️ **Trampa:** una corrida con `AgenteECG` **no genera `EventoPerturbacion`**, así que el resumen
  automático va a decir "Ejecución basal sin perturbaciones." y "Recuperación 100 %", lo cual es
  engañoso. Ver §11.

---

## 7. Fuente externa y CSV

### 7.1 `agente_externo_ecg.py`

- `generar_archivo(ruta: Path, duracion_s, frecuencia_cardiaca_lpm, inicio_arritmia_s, fin_arritmia_s)` (líneas 8-53).
- `frecuencia_muestreo_hz = 250.0` fija; `cantidad = int(duracion_s * 250) + 1` muestras;
  `tiempo = indice / 250`.
- `hay_arritmia = inicio_arritmia_s <= tiempo < fin_arritmia_s` (intervalo semiabierto [5, 14)).
- Durante la arritmia (líneas 31-36), de forma determinista:
  `frecuencia = 145 + 24·sin(2π·0.73·t) + 11·sin(2π·1.37·t)`, `eficiencia = 0.45`,
  `evento = "taquiarritmia"`. Fuera: `frecuencia = frecuencia_cardiaca_lpm` (70), `eficiencia = 1.0`,
  `evento = "ritmo_basal"`.
- Forma de onda: fase acumulada `fase = (fase + FC/(60·250)) % 1`, suma de 5 gaussianas en la fase
  (P 0,12 mV, Q −0,15, R 1,10, S −0,25, T 0,30) más una deriva de línea de base de
  0,015·sin(2π·0,33·t) (líneas 41-49).
- Escribe con `csv.writer`: `round(tiempo, 6)`, `round(amplitud, 6)`, `round(frecuencia, 3)`,
  `eficiencia` (float), `evento`.
- CLI (líneas 56-70): `--salida` (por defecto `resultados/ecg_simulado.csv`, **relativo al
  directorio actual**, no a la ubicación del script), `--duracion` 20, `--frecuencia-cardiaca` 70,
  `--inicio-arritmia` 5, `--fin-arritmia` 14. Valida `0 <= inicio < fin <= duracion`,
  `duracion > 0` y `20 <= FC <= 240`. Crea la carpeta de destino.

### 7.2 Resumen de `CONTRATO_ECG.md`

- Columnas: `tiempo_s`, `ecg_mV`, `frecuencia_cardiaca_lpm`, `eficiencia_ritmo`, `evento`
  (`ritmo_basal` | `taquiarritmia`).
- El agente debe publicar `frecuencia_cardiaca_objetivo` (`latido/min`) y `eficiencia_ritmo`
  (sin unidad → `"1"` en el código) durante la simulación, **sin** modificar las ecuaciones
  cardiovasculares.
- Salida mínima hacia la interfaz: muestras (tiempo y amplitud), origen de la señal, estado de
  calidad (`valido` / `degradado` / `incorrecto`), cantidad de muestras, duración y fs estimada.
- Detección mínima: columnas ausentes, datos no numéricos, menos de dos muestras, tiempos
  repetidos o desordenados. (El enunciado agrega: archivo inexistente, vacíos y rangos de FC
  [20, 240] y eficiencia [0,2, 1,2].)
- Informe: comparar antes / durante / después; gráficas de ECG, FC, VS, GC, PAM y DO2.
- Reutilización: la lectura de la fuente debe estar separada del agente y de la gráfica.
- ⚠️ El ejemplo del contrato (`0.000,0.012,70.0,1.0,ritmo_basal`) **no coincide literalmente** con el
  archivo real: la primera fila real es `0.0,0.0,70.0,1.0,ritmo_basal` (Python escribe `0.0` y no
  `0.000`). El parser no debe depender del formato textual.

### 7.3 Inspección de `resultados/ecg_simulado.csv`

(Script ad hoc ejecutado desde un directorio temporal, sin guardarlo en el proyecto.)

| Medida | Valor |
|---|---|
| Filas de datos | **5001** (+ 1 encabezado) |
| Columnas | `tiempo_s, ecg_mV, frecuencia_cardiaca_lpm, eficiencia_ritmo, evento` |
| Primer / último tiempo | 0.0 s / 20.0 s |
| Δt (min / max / mediana) | 0.003999999999997783 / 0.004000000000001336 / 0.004 s |
| fs = 1/mediana(Δt) | 250.0 Hz (también (N−1)/(tN−t0) = 250.0) |
| Tiempos estrictamente crecientes | Sí |
| `ecg_mV` min / max | −0.255279 / 1.084231 mV |
| `ritmo_basal` | n = 2751; FC = 70.0 (constante); eficiencia = 1.0 |
| `taquiarritmia` | n = 2250; FC ∈ [110.142, 179.005], media ≈ 144.56; eficiencia = 0.45 (constante) |
| Transición basal → taquiarritmia | fila 1250 (índice 0 = primera fila de datos): t = 4.996 (basal) → **t = 5.0** (taquiarritmia, FC 116.684) |
| Transición taquiarritmia → basal | fila 3500: t = 13.996 (taquiarritmia, FC 178.274) → **t = 14.0** (basal, FC 70.0) |
| ¿Igual a regenerarlo? | Sí: `python3 agente_externo_ecg.py --salida <tmp>` produce un archivo idéntico byte a byte (`cmp`) |

Primeras 3 filas de datos:
```
tiempo_s,ecg_mV,frecuencia_cardiaca_lpm,eficiencia_ritmo,evento
0.0,0.0,70.0,1.0,ritmo_basal
0.004,0.000125,70.0,1.0,ritmo_basal
0.008,0.00025,70.0,1.0,ritmo_basal
```
Última fila: `20.0,0.000458,70.0,1.0,ritmo_basal`.

Muestras en tiempos múltiplos de 0,1 s cerca de las transiciones (útil para las pruebas de sincronización):
`t=4.9` → FC 70.0 / ef 1.0; `t=5.0` → FC 116.684 / ef 0.45; `t=5.1` → FC 120.447;
`t=13.9` → FC 167.083 / ef 0.45; `t=14.0` → FC 70.0 / ef 1.0.

Rangos frente al catálogo: FC máx. 179 < 240 (catálogo) y < 220 (límite del cardiovascular);
eficiencia 0,45 y 1,0 ∈ [0,2, 1,2]. El CSV por defecto no provoca errores de dominio.

---

## 8. Interfaz web (`interfaz_web.py`)

### 8.1 Tecnología
- Solo biblioteca estándar: `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler`
  (`interfaz_web.py:5`, `171-196`), en `127.0.0.1:8765` (fijo, `199-206`). `webbrowser.open`
  vía `threading.Timer(0.7, ...)`.
- **HTML, CSS y JS embebidos** en el string `HTML = r'''...'''` (líneas 128-168), todo en
  pocas líneas muy largas. JavaScript plano, sin frameworks ni librerías externas.
  Gráficas con **`<canvas>` 2D**.
- `VERSION_INTERFAZ = "1.3.2-estudiantes"` (línea 11).
- El handler silencia los logs (`log_message` → `pass`).

### 8.2 Rutas
| Método | Ruta | Recibe | Devuelve |
|---|---|---|---|
| GET | `/` (cualquier otra ruta → 404) | — | HTML (`text/html; charset=utf-8`) |
| POST | `/simular` | JSON (cuerpo leído con `Content-Length`) | JSON `simular(datos)` |
| POST | `/sensibilidad` | JSON | JSON `analizar_sensibilidad(datos)` |
| POST | otra | — | 404 |

- Cualquier excepción en un POST → **HTTP 400** con `{"error": "<str(error)>"}`
  (`interfaz_web.py:186-187`). El servidor no se cae.
- Todas las respuestas llevan `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` y
  `Pragma: no-cache` (191-192). El JS además agrega `?instante=Date.now()` y `cache:'no-store'`.

**Request `/simular`** (`simular`, líneas 34-92). Claves leídas:
`escenario` (por defecto `"basal"`), `duracion_s` (por defecto la del escenario; rango 1–600),
`paso_s` (por defecto 0.1; rango (0, 1]), `volumen_sanguineo`, `resistencia` (→
`resistencia_vascular_sistemica`), `contractilidad`, `factor_ventilatorio`, `hemoglobina`,
`bicarbonato`, `comparar_basal` (bool), `eventos_personalizados`
(lista de `{variable, tiempo_s, valor, duracion_s?}`) o el formato legado
`usar_evento_personalizado` / `variable_evento` / `tiempo_evento_s` / `valor_evento`.
El navegador envía los valores de los inputs **como strings**; el servidor los convierte con `float()`.

Flujo: arma los eventos → `crear_motor_referencia(paso_s, eventos)` → aplica los parámetros con
`motor.estado.aplicar_evento` (productor `"interfaz"`, validando dominio) → `motor.ejecutar(duracion)`
→ **submuestrea** `historial[::max(1, len//1200)]` → `analizar_historial` **sobre el historial ya
submuestreado**.

**Response `/simular`** (verificada llamando a `simular({"escenario": "hemorragia"})` desde una
copia del proyecto y pasándola por `json.dumps`/`json.loads`; 90 s → `len(historial) = 901`):
```json
{
  "historial": [
    {"ciclo": 0, "tiempo_s": 0.0, "frecuencia_cardiaca": 70.0, "volumen_sistolico": 70.0,
     "gasto_cardiaco": 4.9, "aporte_sistemico_o2": 970.0, "presion_arterial_media": 90.2,
     "volumen_sanguineo": 5.0, "contractilidad": 1.0, "frecuencia_cardiaca_objetivo": 0.0,
     "eficiencia_ritmo": 1.0, "resistencia_vascular_sistemica": 18.0, "frecuencia_respiratoria": 12.0,
     "factor_ventilatorio": 1.0, "hemoglobina": 15.0, "bicarbonato": 24.0, "ventilacion_minuto": 6.0,
     "ventilacion_alveolar": 4.32, "presion_arterial_co2": 40.0, "presion_arterial_o2": 90.0,
     "saturacion_arterial_o2": 97.0, "contenido_arterial_o2": 19.8, "ph_arterial": 7.4,
     "actividad_simpatica": 1.0, "actividad_parasimpatica": 1.0, "impulso_respiratorio": 1.0},
    "... una fila por ciclo (submuestreada si hay > 2400 filas) ..."
  ],
  "eventos": [{"nombre": "perdida_volumen", "tiempo_s": 10.0, "duracion_s": 0.0, "cambios": {"volumen_sanguineo": 4.0}}],
  "variables": {"frecuencia_cardiaca": "Frecuencia cardiaca (latido/min)", "...": "las 12 claves de VARIABLES"},
  "analisis": {
    "metricas": {
      "presion_arterial_media": {"basal": 90.2, "minimo": 79.33011149195697, "tiempo_minimo_s": 12.7,
        "maximo": 90.2, "tiempo_maximo_s": 0.0, "final": 85.6223494074264,
        "cambio_final_porcentaje": -5.075000656955216, "recuperacion_porcentaje": 57.886867108283305},
      "...": "una entrada por cada nombre de VARIABLES_CLAVE"
    },
    "resumen": ["Se aplicaron 1 evento(s): perdida_volumen.",
                "La presión arterial descendió más de 5 % respecto de la referencia.",
                "Apareció activación simpática compensatoria dentro del modelo.",
                "El aporte sistémico de oxígeno disminuyó más de 10 %."]
  }
}
```
Con `"comparar_basal": true` se agrega `"historial_referencia"` (misma forma que `historial`;
601 filas para 60 s), calculado con `ESCENARIOS["basal"].crear_motor(paso_s=0.1)`.
Error de ejemplo (400): `{"error": "La duracion debe estar entre 1 y 600 segundos"}`.
(El submuestreo usa `salto = max(1, len // 1200)`, así que recién con ≥ 2400 filas el salto es ≥ 2.)

**`/sensibilidad`** (`analizar_sensibilidad`, 95-125): llama a `simular` con `paso_s` ∈
(0.05, 0.10, 0.20, 0.50) y `comparar_basal=False`, y devuelve
`{"filas": [{"paso_s", "pam_minima", "fc_maxima", "paco2_maxima", "aporte_o2_minimo", "diferencia_maxima_porcentaje", "aceptable"}], "criterio_porcentaje": 2.0}`.
Como reutiliza `simular(datos)`, cualquier dato ECG que se agregue al request también pasa por acá.

### 8.3 `VARIABLES` (etiquetas y curvas seleccionables, líneas 18-31)
`frecuencia_cardiaca`, `presion_arterial_media`, `gasto_cardiaco`, `contenido_arterial_o2`,
`aporte_sistemico_o2`, `presion_arterial_co2`, `presion_arterial_o2`, `saturacion_arterial_o2`,
`ph_arterial`, `frecuencia_respiratoria`, `actividad_simpatica`, `actividad_parasimpatica`.
⚠️ **No están `volumen_sistolico`** (gráfica obligatoria), `frecuencia_cardiaca_objetivo` ni
`eficiencia_ritmo`, así que hoy no se pueden graficar aunque estén en el historial. Las etiquetas
no llevan tildes.

### 8.4 Front-end: flujo y gráficas (todo dentro de `HTML`, líneas 147-167)
- Estado global JS: `resultado` (última respuesta) y `eventosPersonalizados`.
- **`ejecutar(boton)`** (línea 153): lee los inputs, hace `fetch('/simular?instante=…', {method:'POST', ...})`,
  guarda `resultado`, llama a `crearSelectores()` **solo la primera vez** (guarda
  `if(!document.querySelector('#variables input'))`), limpia `#graficas`, `mostrarAnalisis()` y
  `requestAnimationFrame(dibujarTodo)`. Si hay error: `Error: <mensaje>` en `#estado`.
- **`crearSelectores()`** (161): un checkbox por entrada de `resultado.variables`; preseleccionadas
  `frecuencia_cardiaca`, `presion_arterial_media`, `presion_arterial_co2`, `frecuencia_respiratoria`.
- **`dibujarTodo()`** (162): por cada variable tildada crea `div.grafica` con `<h3>`, un `<canvas>`
  de **700×300** (resolución interna; CSS `width:100%; height:260px`) y `div.resumen`; luego llama a
  `dibujar(...)` y `activarTooltipFisiologico(canvas, k)`.
- **`dibujar(c, res, k)`** (163):
  1. `x.clearRect(0,0,w,h)` (**limpieza completa** al inicio de cada redibujo).
  2. Margen `m=45`; escala Y con min/max de los datos (+ referencia), con 8 % de margen; si min==max, ±1.
  3. 5 líneas horizontales de grilla `#d7dee6` con etiquetas `toFixed(1)`.
  4. Por cada evento en `resultado.eventos`: línea vertical punteada naranja `#d35400`
     (`setLineDash([5,4])`) + nombre del evento.
  5. `trazar(...)` de la curva en `#1677b8`, `lineWidth 2.5`; si hay referencia, punteada `#8293a5`
     + leyenda "Configurado"/"Basal".
  6. Ejes: "0 s", "<tfinal> s", "Tiempo (s)", "Valor" rotado. Resumen de texto
     `Inicial · Min · Max · Final`.
- **`trazar(x,datos,k,ts,ymin,ymax,w,h,m,color,punteada)`** (164): mapeo
  `px = m + (w-2m)·(t−t0)/(tN−t0)`, `py = h − m − (h−2m)·(v−ymin)/(ymax−ymin)`.
- **Mouse — `activarTooltipFisiologico(c, k)`** (167):
  - `c.onmousemove`: convierte `clientX` a coordenadas del canvas
    (`(e.clientX-r.left)*c.width/r.width`), calcula `fraccion` en [0,1] dentro del área útil y
    toma el índice `i = Math.round(fraccion*(datos.length-1))` (**supone muestreo uniforme**).
    Luego **redibuja todo el canvas con `dibujar(...)`** (eso es lo que borra el indicador anterior),
    recalcula `px, py` del punto y llama a `dibujarCruceta`. Muestra el tooltip con
    `<b>etiqueta</b><br>Tiempo: X.XX s<br>Valor: Y.YYY` en `clientX+12, clientY+12`.
  - `c.onmouseleave`: redibuja con `dibujar(...)` (sin cruceta) y oculta el tooltip.
- **`dibujarCruceta(c, px, py, m)`** (166): `setLineDash([6,5])`, `strokeStyle '#263746'`,
  `lineWidth 1.2`, una línea vertical y otra horizontal que cruzan el área útil, más un círculo
  relleno de radio 4 en el punto.
- **`obtenerTooltip(c)`** (165): crea o reutiliza un `div.tooltip-grafica` (CSS `position:fixed`,
  `pointer-events:none`) dentro del contenedor del canvas.
- Otras funciones: `mostrarAnalisis`, `sensibilidad`, `restaurar`, `exportar` (CSV del historial
  en el navegador), `exportarExperimento` / `cargarExperimento` (JSON), `agregarEvento`,
  `quitarEvento`, `mostrarEventos`.
- El `<select id="escenario">` está **hardcodeado** en el HTML (línea 132) y también en la
  validación de `cargarExperimento` (línea 160).
- Ya existe una sección de marcador de posición: *"Actividad obligatoria: agente externo de ECG
  — Integración pendiente…"* (línea 146), a lo ancho de la grilla (`grid-column:1/-1`).

### 8.5 Subida de archivos
- **No hay ningún endpoint de subida** (ni multipart ni ruta de archivos). El servidor solo
  acepta JSON en `/simular` y `/sensibilidad`.
- Sí hay un patrón **del lado del cliente** que se puede reutilizar:
  `<input id="archivo_experimento" type="file" accept="application/json,.json" hidden onchange="cargarExperimento(this)">`,
  disparado por un botón (línea 144). En `cargarExperimento` se lee con
  `await input.files[0].text()` y al final se hace `input.value=''` para poder volver a elegir
  el mismo archivo (línea 160).
- Para el CSV hay dos caminos posibles: leer el texto en el navegador y enviarlo dentro del JSON
  (por ejemplo, en `/simular` o en una ruta nueva para validar y previsualizar), o agregar una
  ruta nueva. El CSV pesa unos 200 KB y no hay límite explícito de `Content-Length`.
  ⚠️ A confirmar el diseño.

---

## 9. Pruebas

### 9.1 Estructura de `pruebas/test_paciente_virtual.py`
- Agrega `src` a `sys.path` (línea 5) e importa `crear_motor_referencia`, los tres agentes,
  `EventoPerturbacion` y `analizar_historial`.
- Una sola clase, `PruebasPacienteVirtual(unittest.TestCase)`, con 25 métodos:

| # | Prueba | Qué verifica |
|---|---|---|
| 1 | `test_estado_basal_permanece_estable` | 10 s basal: FC = 70, PAM ≈ 90,2, PaCO2 ≈ 40 |
| 2 | `test_el_estado_avanza_por_ciclos` | un ciclo con dt 0,2 → `ciclo == 1`, `tiempo_s == 0.2` |
| 3 | `test_respiratorio_basal_calcula_ventilacion_alveolar` | VE 6,0, VA 4,32, PaO2 > 85, SaO2 > 95, CaO2 > 19, pH ≈ 7,40 |
| 4 | `test_hemoglobina_baja_reduce_aporte_de_oxigeno` | Hb 8 → menos CaO2 y menos DO2 |
| 5 | `test_co2_elevado_reduce_ph_estimado` | PaCO2 60 → pH < 7,40 |
| 6 | `test_hipoventilacion_aumenta_objetivo_de_co2` | bucle manual del respiratorio con impulso 0,5 → PaCO2 > 65, SaO2 < 95 |
| 7 | `test_hiperventilacion_reduce_co2` | impulso 1,5 → FR > 12, PaCO2 < 40 |
| 8 | `test_cardiovascular_basal` | VS = 70, GC ≈ 4,9, PAM ≈ 90,2 |
| 9 | `test_estimulo_simpatico_aumenta_frecuencia_y_gasto` | simpático 1,5 → FC y GC suben |
| 10 | `test_reduccion_de_volumen_disminuye_volumen_sistolico` | Vsang 4 → VS y GC bajan |
| 11 | `test_aumento_resistencia_eleva_presion_y_reduce_volumen_sistolico` | RVS 24 → VS baja, PAM sube |
| 12 | `test_nervioso_basal_permanece_en_equilibrio` | simp = para = impulso = 1 |
| 13 | `test_hipotension_activa_simpatico_y_retira_parasimpatico` | PAM 70 → simp ↑, para ↓ |
| 14 | `test_hipertension_reduce_simpatico_y_aumenta_parasimpatico` | PAM 115 → simp ↓, para ↑ |
| 15 | `test_hipercapnia_e_hipoxemia_aumentan_impulso` | PaCO2 50 y PaO2 55 → impulso ↑ y simp ↑ |
| 16 | `test_evento_se_aplica_una_sola_vez_en_el_tiempo_programado` | evento a 0,2 s: se aplica 1 vez y deja el valor final |
| 17 | `test_hemorragia_reduce_presion_y_activa_barorreflejo` | evento a 2 s: PAM ↓, simpático > 1 |
| 18 | `test_eventos_sucesivos_conservan_el_ultimo_valor` | dos eventos → queda el último |
| 19 | `test_rampa_alcanza_valores_intermedios_y_final` | rampa de 2 s: valor intermedio ≈ 4,5 y final 4,0 |
| 20 | `test_rampa_con_duracion_negativa_es_rechazada` | `ValueError` |
| 21 | `test_analisis_detecta_caida_de_presion_y_respuesta_simpatica` | métricas y texto con "simpática" |
| 22 | `test_analisis_basal_informa_estabilidad` | resumen con "basal", recuperación ≥ 99 |
| 23 | `test_resultados_son_consistentes_con_diferentes_pasos` | PAM mínima con dt 0,05/0,1/0,2/0,5 dentro del 2 % |
| 24 | `test_instantanea_no_admite_escritura` | `TypeError` al escribir en `variables` |
| 25 | `test_co2_elevado_activa_control_y_luego_disminuye` | PaCO2 55 → impulso > 1,1 y PaCO2 final < 55 |

### 9.2 Patrones reutilizables para las pruebas nuevas
- **Bootstrap de imports:** `sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))`
  y después `from paciente_virtual.<modulo> import ...` (imports **absolutos** del paquete).
- **Probar un agente aislado:** construir un motor de referencia para obtener una instantánea
  válida y llamar al agente directamente:
  `{p.variable: p.valor for p in Agente().calcular(motor.estado.instantanea(), 0.1)}`.
- **Instantánea a un tiempo arbitrario** (útil para la sincronización del ECG): construir
  `InstantaneaEstado(ciclo, tiempo_s, variables)` a mano, como hace la prueba 6 (líneas 55-63).
  Para verificar unidades, comparar `p.unidad` en la lista de `Publicacion`.
- **Simulación integrada:** `historial = motor.ejecutar(T)`; buscar filas por tiempo con
  `min(historial, key=lambda f: abs(f["tiempo_s"] - t))` (prueba 19); en dt 0,1 el índice
  `historial[i]` corresponde a t = i·0,1 (prueba 17 usa `historial[20]` = t 2,0).
- **Errores esperados:** `with self.assertRaises(ValueError): ...`.
- Para CSV de prueba, `tempfile` + escribir texto (no hay helpers existentes para eso).
- `pruebas/__init__.py` existe, y por eso funciona `-t .`; un archivo nuevo `pruebas/test_agente_ecg.py`
  lo encuentra el `discover` automáticamente.

### 9.3 Resultado de `python3 -m unittest discover -s pruebas -t . -v`

**Con `python3` del entorno (pyenv 3.9.18): FALLA al importar.**
```
ERROR: pruebas.test_paciente_virtual (unittest.loader._FailedTest)
ImportError: Failed to import test module: pruebas.test_paciente_virtual
  File ".../src/paciente_virtual/motor.py", line 25, in MotorSimulacion
    eventos: list[EventoPerturbacion] | None = None):
TypeError: unsupported operand type(s) for |: 'types.GenericAlias' and 'NoneType'
Ran 1 test in 0.000s
FAILED (errors=1)
```

**Con `/usr/bin/python3.12` (3.12.3): las 25 pruebas pasan.**
```
Ran 25 tests in 0.084s
OK
```

---

## 10. Línea de base

Para no escribir en `resultados/` del proyecto, los scripts se ejecutaron sobre una **copia** del
proyecto en un directorio temporal, con Python 3.12:

```
$ python3.12 ejecutar_escenarios.py
basal                FC=  70.0 PAM=  90.2 PaCO2= 40.0 -> basal.csv
hemorragia           FC=  78.5 PAM=  85.6 PaCO2= 40.0 -> hemorragia.csv
aumento_resistencia  FC=  62.3 PAM=  94.4 PaCO2= 40.0 -> aumento_resistencia.csv
hipoventilacion      FC=  70.6 PAM=  92.1 PaCO2= 49.6 -> hipoventilacion.csv

$ python3.12 ejecutar_simulacion.py        # NO es basal: arranca con PaCO2 = 55
Simulacion terminada: 300 ciclos
Frecuencia cardiaca final: 70.00 latido/min
Presion arterial media final: 90.22 mmHg
Presion arterial de CO2 final: 40.02 mmHg
```

Esos scripts solo imprimen FC, PAM y PaCO2. Para el resto de las variables se usó
`crear_motor_referencia()` (= escenario `basal`, dt 0,1 s, 60 s) en memoria:

| Variable | t = 0 (inicial) | t = 10 s | t = 60 s |
|---|---|---|---|
| `frecuencia_cardiaca` (latido/min) | 70.000 | 70.000 | 70.000 |
| `volumen_sistolico` (mL/latido) | 70.000 | 70.000 | 70.000 |
| `gasto_cardiaco` (L/min) | 4.900 | 4.900 | 4.900 |
| `presion_arterial_media` (mmHg) | 90.200 | 90.200 | 90.200 |
| `aporte_sistemico_o2` (mL/min) | 970.000 | 961.797 | **961.794** |
| `contenido_arterial_o2` (mL/dL) | 19.800 | 19.628 | 19.628 |
| `actividad_simpatica` / `actividad_parasimpatica` | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |

⚠️ El `aporte_sistemico_o2` inicial (970) **no es el de equilibrio**: el valor inicial de
`contenido_arterial_o2` es 19,8, pero el respiratorio calcula 19,628 desde el primer ciclo, así que
el aporte converge a **≈ 961,8 mL/min**. Para el informe conviene tomar ≈ 961,8 como basal.
En t = 60 s todas las variables cardiovasculares tienen productor `cardiovascular`, y
`frecuencia_cardiaca_objetivo`/`eficiencia_ritmo` siguen con productor `condicion_inicial`.

### Emulación aproximada (NO es la solución ni un resultado esperado)

Solo para dimensionar los efectos, se emuló el episodio con dos `EventoPerturbacion`
(mecanismo existente): a 5 s, `frecuencia_cardiaca_objetivo = 145` (escalón constante, **no** la FC
sinusoidal del CSV) y `eficiencia_ritmo = 0.45`; a 14 s se vuelve a `0`/`1.0`. Por la semántica
de §4.4, un agente real reaccionaría **un ciclo más tarde** que esto.

| Fase | FC | VS | GC | PAM | DO2 | simp / para |
|---|---|---|---|---|---|---|
| Antes (t ≤ 5,0) | 70 | 70 | 4,90 | 90,2 | 961,8 | 1,00 / 1,00 |
| Inicio (t = 5,1) | 72,5 | **31,5** (salto) | 2,28 | 87,8 | 448 | 1,00 / 1,00 |
| t = 8 | 117,9 | 35,0 | 4,13 | ≈ 70,6 (mín. ≈ 69,1) | 810 | 1,46 / 0,25 |
| Fin del episodio (t = 14,0) | 141,5 | 34,4 | 4,86 | 88,4 | 954 | 1,36 / 0,88 |
| Rebote (t = 14,1) | 139,4 | 76,2 | **10,63** | 93,6 | **2086** | 1,35 / 0,88 |
| t ≈ 15–17 | 122 → 89 | 72,5 → 64,6 | 8,9 → 5,8 | 123,7 → **131,3 (pico, t = 15,9)** → 124,7 | 1742 → 1130 | 0,67 / 1,93 (t=17) |
| Valle (t ≈ 20–22) | mín. 60,7 (t = 20,8) | — | mín. 3,81 (t = 20,1) | mín. 79,2 (t = 22,1) | mín. 748 (t = 20,1) | — |
| t = 20 | 61,9 | 61,6 | 3,82 | 88,2 | 749 | 0,54 / 1,33 |
| t = 30 | 70,0 | 69,3 | 4,85 | 91,6 | 952 | 0,96 / 1,09 |
| t = 40 | 70,1 | 70,0 | 4,91 | 90,5 | 963 | 1,00 / 1,01 |

Variante con `frecuencia_cardiaca_objetivo = 70` (en lugar de 0) después de 14 s: en t = 20,
FC 79,3, PAM 100,5, GC 4,69; en t = 30, FC 70,3 y PAM 89,9. **La recuperación difiere** según la
decisión de §5.

Lecturas cualitativas útiles para el informe: el VS y el GC caen **de inmediato** (la eficiencia
no tiene τ); la FC sube con τ = 3 s; la PAM cae con τ = 2 s y activa el barorreflejo; al
terminar hay un **rebote** de GC/DO2/PAM porque la eficiencia vuelve a 1 de golpe mientras la FC
sigue alta, y después una **oscilación amortiguada** por el barorreflejo (≈ 25–40 s para volver al
basal). Una simulación de 20 s (la duración del CSV) **corta la recuperación** a mitad de camino.

---

## 11. Puntos de integración para el obligatorio (sin implementar)

### Dónde tocar
1. **Crear `src/paciente_virtual/ecg.py`** (nombre sugerido por el enunciado), con dos piezas
   separadas:
   - un **lector/fuente** (CSV → muestras validadas + metadatos de calidad), sin código de
     visualización, reemplazable por otra fuente (hardware/IA);
   - **`AgenteECG`**, que cumpla el `Protocol` `Agente`: `identificador = "agente_ecg"`,
     `entradas = frozenset()`,
     `salidas = frozenset({"frecuencia_cardiaca_objetivo", "eficiencia_ritmo"})` y
     `calcular(self, estado: InstantaneaEstado, paso_s: float) -> list[Publicacion]`,
     que use `estado.tiempo_s` para elegir la muestra y devuelva
     `Publicacion("frecuencia_cardiaca_objetivo", v, "latido/min")` y
     `Publicacion("eficiencia_ritmo", v, "1")`.
   - Imports **relativos** dentro del paquete, como en los demás módulos:
     `from .agentes import Publicacion` y `from .estado import InstantaneaEstado, CalidadDato`.
2. **Registrar el agente** en la lista de `configuracion.py:67`, por ejemplo con un parámetro
   opcional nuevo en `crear_motor_referencia` (p. ej. `agentes_extra` o `agente_ecg`, cuyo valor por
   defecto sea `None` para no romper las 25 pruebas), o construyendo `MotorSimulacion` en la
   interfaz con la lista extendida. El catálogo y los valores iniciales **ya incluyen** las dos
   variables.
3. **`interfaz_web.py`**:
   - `simular(datos)` (línea 34): aceptar la señal o el CSV en el JSON y pasarla a la
     construcción del motor (línea 60). Validar antes de simular y devolver un error 400
     comprensible si la señal es inválida.
   - Posible ruta nueva en `do_POST` (línea 179, conjunto `{"/simular", "/sensibilidad"}`) para
     **cargar y validar** el CSV y devolver las muestras y los metadatos (nombre, calidad, n,
     duración, fs, min/max) sin simular. O hacerlo todo en `/simular`. ⚠️ A confirmar.
   - Agregar `volumen_sistolico` (y quizás `frecuencia_cardiaca_objetivo` y `eficiencia_ritmo`)
     a `VARIABLES` (líneas 18-31).
   - En `HTML`: reemplazar el marcador de la línea 146 por la sección de ECG (input de archivo
     con el patrón de `archivo_experimento`, nombre del archivo, calidad, n, duración, fs, min/max,
     canvas del ECG con cruceta y tooltip que imiten `dibujar`/`dibujarCruceta`/
     `activarTooltipFisiologico`) y enviar la señal en `ejecutar()` (línea 153).
   - Marcar el inicio y el fin de la arritmia en las gráficas fisiológicas: hoy las líneas
     naranjas salen **solo** de `resultado.eventos` (`motor.eventos_aplicados`), y el agente no
     genera eventos.
4. **`src/paciente_virtual/__init__.py`**: opcionalmente exportar `AgenteECG` y el lector
   (hoy exporta solo `CalidadDato`, `EstadoFisiologicoGlobal`, `ValorFisiologico`, `MotorSimulacion`).
   No es necesario: las pruebas importan por submódulo.
5. **`pruebas/test_agente_ecg.py`** con las 5 pruebas mínimas del enunciado.
6. Opcional: `analisis.py` (`VARIABLES_CLAVE` sin `volumen_sistolico`; resumen engañoso sin eventos).

### Riesgos y trampas detectados
- **Python 3.9 en `python3`** (§1, §9): las pruebas y los scripts fallan. Hay que ejecutar con 3.10+
  y avisarlo en las instrucciones de entrega.
- **Nombres y unidades exactos:** `frecuencia_cardiaca_objetivo` / `"latido/min"`,
  `eficiencia_ritmo` / `"1"`. Una diferencia de unidad lanza `ValueError("Unidad incorrecta para ...")`
  a mitad de la simulación (→ 400 en la interfaz). Publicar en `calcular` un nombre que no está en el catálogo
  lanza `KeyError` (`motor.py:60`). Un nombre mal escrito en `salidas` se detecta al construir el
  motor (`"Variables ausentes del catalogo"`, `motor.py:50-52`). Lo que **no** se detecta es
  publicar en `calcular` una variable que **falta** en `salidas` (o un error de tipeo en `salidas`
  que coincida con otro nombre real del catálogo): no da error y la validación de productores
  duplicados deja de proteger esa variable.
- **Dominio del catálogo:** FC objetivo en [0, 240] y eficiencia en [0,2, 1,2]. Un CSV con valores
  fuera de rango que pase la validación del lector haría fallar al motor. Conviene validar en el
  lector con los mismos rangos (el enunciado sugiere FC en [20, 240]).
- **`frecuencia_cardiaca_objetivo = 0` es un centinela** ("sin control externo"). Publicar 70 en
  ritmo basal anula el barorreflejo sobre la FC (§5). Hay que decidirlo y justificarlo.
- **Fin de las muestras:** el CSV dura 20 s y la interfaz simula 60 s por defecto. Hay que definir
  qué se publica después de la última muestra (mantener la última, volver a 0/1.0, dejar de publicar
  → el motor conserva el último valor confirmado). Si la simulación arranca en t = 0 y el CSV
  empieza en otro t, también hay que definir qué pasa antes de la primera muestra.
- **Duración < 14 s:** la arritmia (5–14 s) quedaría incompleta o ausente. La interfaz acepta
  desde 1 s. Para ver la recuperación hacen falta ≳ 30–40 s (§10).
- **Retardo de un ciclo** entre publicación y efecto (§4.4). Se puede documentar como parte de la
  estrategia de sincronización.
- **Comparación de tiempos flotantes** (`round(..., 12)` vs 6 decimales del CSV): usar tolerancia
  o `bisect`, nunca `==`.
- **Estado del agente entre corridas:** la interfaz crea un motor nuevo en cada `/simular`; si el
  `AgenteECG` guarda un índice o puntero interno, hay que crear una instancia nueva por simulación
  (o indexar siempre por `estado.tiempo_s`, sin estado mutable) para que el resultado sea reproducible.
  `/sensibilidad` también re-simula con dt 0,05–0,5.
- **Submuestreo** a ≈ 1200 filas: el historial fisiológico con dt 0,1 y 60 s (601 filas) no se
  submuestrea, pero el ECG crudo (5001 muestras) no pasa por el historial y habrá que enviarlo aparte.
  ⚠️ A confirmar si se decima para dibujar; con 5001 puntos, `Math.min(...array)` en JS funciona.
- **Tooltip por índice uniforme:** `activarTooltipFisiologico` asume muestras equiespaciadas. Para
  el ECG funciona (Δt constante), pero buscar por tiempo es más robusto.
- **Resumen automático engañoso:** sin eventos, `analizar_historial` dice "Ejecución basal…" y
  recuperación 100 %.
- **`comparar_basal` y registro incondicional:** la curva gris "Basal" se calcula con
  `ESCENARIOS["basal"].crear_motor(paso_s=0.1)` → `crear_motor_referencia`. Si el `AgenteECG` se
  agrega siempre en `configuracion.py:67`, la referencia "basal" también tendría la arritmia (y
  además cambiarían las 25 pruebas y los escenarios). Por eso conviene que el registro sea opcional.
- **`crearSelectores` corre una sola vez:** si se agregan claves a `VARIABLES`, aparecen al recargar
  la página, no entre ejecuciones de la misma sesión.
- **Servidor viejo / caché:** el HTML está embebido en el `.py`, así que cualquier cambio exige
  **reiniciar el proceso** (Ctrl+C y volver a lanzar). Si queda otro servidor corriendo, el puerto
  8765 fijo dará "Address already in use" o se seguirá viendo la versión anterior. El caché del
  navegador ya está desactivado (`no-store`, `?instante=`). Conviene actualizar `VERSION_INTERFAZ`
  para comprobar qué versión se está viendo.
- **Rutas relativas al cwd:** `agente_externo_ecg.py` escribe en `resultados/ecg_simulado.csv` relativo
  al directorio actual. `ejecutar_simulacion.py` usa `RAIZ_PROYECTO`. Hay que ejecutar todo desde la raíz.
- **Reemplazar el archivo sin reiniciar:** volver a poner `input.value=''` después de leerlo (como en
  `cargarExperimento`) para que `onchange` se dispare con el mismo nombre. Si la carga falla, limpiar
  las gráficas y el `resultado` anteriores para que no parezcan del archivo nuevo.

---

## 12. Preguntas abiertas (⚠️ A confirmar)

1. ¿El motor debería verificar que un agente publique solo sus `salidas` declaradas? Hoy no lo
   hace (§3.1).
2. ¿La calidad de la señal (`valido` / `degradado` / `incorrecto`) reutiliza `CalidadDato` (que no
   tiene `incorrecto`) o es un tipo propio del lector? (§3.1)
3. ¿Cómo registrar el `AgenteECG`: parámetro opcional en `crear_motor_referencia`, función nueva o
   motor armado en la interfaz? (§4.2)
4. En los tramos `ritmo_basal`, ¿publicar `frecuencia_cardiaca_objetivo = 70` (lo literal del CSV, que
   anula el barorreflejo sobre la FC) o 0 (devuelve el control al sistema nervioso)? (§5)
5. ¿Qué publicar antes de la primera muestra y después de la última (CSV de 20 s, simulación de 60 s)? (§11)
6. Diseño del transporte del CSV: ¿texto dentro del JSON de `/simular`, ruta nueva de carga y
   validación, o ambas? (§8.5, §11)
7. ¿Se decima el ECG para dibujarlo o se envían las 5001 muestras? (§11)
8. El ejemplo de `CONTRATO_ECG.md` (`0.000,0.012,...`) no coincide literalmente con el CSV real
   (`0.0,0.0,...`). Es solo ilustrativo; el parser debe ser tolerante al formato (§7.2).
9. ¿Se debe adaptar `analizar_historial` / el resumen automático para corridas con ECG (hoy dicen
   "basal" y 100 % de recuperación), y marcar inicio y fin de la arritmia en las gráficas? (§6, §11)
