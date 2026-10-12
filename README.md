# Paciente Virtual: integración de una fuente externa de ECG

**Obligatorio 1, Fundamentos de Ingeniería Biomédica.** Facultad de Ingeniería, Universidad ORT Uruguay, 2026.
**Equipo:** Renzo Donagrandi (315078) y Facundo Iraola (244141).

El Paciente Virtual es un simulador educativo formado por agentes (cardiovascular,
respiratorio y nervioso) que intercambian variables a través de un Estado Fisiológico
Global (EFG) coordinado por un motor de paso fijo. En este obligatorio se agregó un
**agente integrador de ECG**. El agente lee una señal externa (20 s a 250 Hz, con una
taquiarritmia entre los 5 y los 14 s), la valida, la sincroniza con el reloj del motor y
publica `frecuencia_cardiaca_objetivo` y `eficiencia_ritmo`. Así la arritmia modifica
de verdad la frecuencia cardíaca, el volumen sistólico, el gasto cardíaco, la presión
arterial media y el aporte sistémico de oxígeno del paciente.

> Proyecto con fines exclusivamente educativos. No diagnostica arritmias ni debe
> usarse para decisiones clínicas.

## Inicio rápido

Requiere Python 3.10 o posterior. No usa bibliotecas externas. Desde esta carpeta:

```bash
python3 agente_externo_ecg.py                      # genera resultados/ecg_simulado.csv
python3 interfaz_web.py                            # abre http://127.0.0.1:8765
python3 -m unittest discover -s pruebas -t . -v    # 43 pruebas
```

En la interfaz: **Seleccionar CSV de ECG** → `resultados/ecg_simulado.csv` → duración
de 60 s → **Ejecutar simulacion**. Los requisitos, la ejecución sin interfaz, los
archivos de prueba y los problemas frecuentes se detallan en
[INSTRUCCIONES.md](INSTRUCCIONES.md).

## Contenido del repositorio

| Ruta | Contenido |
|---|---|
| `informe/Informe Obligatorio 1 - FIB.docx` | Informe técnico: arquitectura, resultados y discusión. |
| `informe/` | Scripts, datos y figuras que reproducen los resultados del informe ([detalle](informe/README.md)). |
| `src/paciente_virtual/` | Paquete del simulador: motor, estado, agentes y el agente ECG. |
| `interfaz_web.py` | Servidor local y página web, con la sección de ECG. |
| `ejecutar_simulacion_ecg.py` | Simulación acoplada y análisis por fases desde la terminal. |
| `pruebas/` | Pruebas automáticas (`unittest`). |
| `datos_prueba/` | CSV válidos, degradado e inválidos para probar la validación. |
| `agente_externo_ecg.py`, `CONTRATO_ECG.md` | Fuente externa y contrato entregados con la letra (sin cambios). |
| `INSTRUCCIONES.md` | Instalación y ejecución paso a paso. |

## Arquitectura

La solución respeta la cadena de capas de la letra y del manual de diseño. Cada capa
conoce únicamente a la siguiente:

```text
agente_externo_ecg.py           fuente externa (entregada)
        ↓  CSV
fuente_ecg.py                   lectura y validación → SenalECG (sin motor ni dibujo)
        ↓  contrato FuenteMuestrasECG
ecg.py · AgenteECG              sincronización con el tiempo del motor → 2 publicaciones
        ↓  Publicacion(variable, valor, unidad, calidad)
motor.py + estado.py            valida nombre, unidad y dominio; confirma en el EFG
        ↓  instantánea del ciclo siguiente
AgenteCardiovascular            consume las dos entradas (ecuaciones sin cambios)
        ↓  historial
interfaz_web.py                 transporta el archivo y dibuja; no calcula fisiología
```

- **El modelo no conoce el ECG.** El agente cardiovascular lee
  `frecuencia_cardiaca_objetivo` y `eficiencia_ritmo` desde el EFG, igual que
  cualquier otra variable. No se modificó ninguna ecuación fisiológica.
- **El agente no conoce el CSV.** `AgenteECG` acepta cualquier objeto que cumpla
  `FuenteMuestrasECG`, así que un dispositivo, una IA o un programa en red pueden
  reemplazar al CSV sin tocar el agente, el motor ni las gráficas.
- **La interfaz no valida ni calcula.** El navegador envía el texto del CSV y el
  servidor lo valida con `fuente_ecg.py`, tanto al cargarlo como al simular.

### Contrato del agente

| | |
|---|---|
| `identificador` | `"agente_ecg"` |
| `entradas` | `frozenset()`: no consume variables fisiológicas, solo `estado.tiempo_s` y `paso_s`. |
| `salidas` | `frecuencia_cardiaca_objetivo` (`"latido/min"`, 0 a 240) y `eficiencia_ritmo` (`"1"`, 0,2 a 1,2) |
| Registro | `crear_motor_referencia(agentes_adicionales=[AgenteECG(senal)])` |

| Columna del CSV | Uso |
|---|---|
| `frecuencia_cardiaca_lpm` | Se publica como `frecuencia_cardiaca_objetivo`. |
| `eficiencia_ritmo` | Se publica como `eficiencia_ritmo`. |
| `tiempo_s` | Sincronización con el motor. |
| `ecg_mV` | Solo para graficar. |
| `evento` | Marca el inicio y el fin de cada episodio. |

### Sincronización temporal

El ECG tiene 250 muestras por segundo y el motor avanza de a 0,1 s. En el ciclo con
tiempo `t` y paso `Δt`, el agente **promedia la frecuencia y la eficiencia de las
muestras del intervalo (t − Δt, t]**. Solo usa muestras del pasado, como haría una fuente
en tiempo real. Como los intervalos no se superponen y cubren todo el tiempo, cada
muestra se usa exactamente una vez.

| Situación | Qué publica el agente | Calidad |
|---|---|---|
| Hay muestras en el intervalo | Su promedio | La de la señal |
| Intervalo vacío porque `Δt` es menor que el período de muestreo | La última muestra anterior | La de la señal |
| La señal ya terminó | La última muestra (en `ecg_simulado.csv`, ritmo basal) | `degradado` |
| Todavía no hay ninguna muestra | FC 0 («sin control externo», según el catálogo) y eficiencia 1 | `valido` |

El agente no guarda estado entre ciclos, así que dos simulaciones iguales dan el mismo
resultado. Por la instantánea común del motor, lo que se publica en un ciclo lo lee el
modelo cardiovascular en el siguiente: el efecto aparece 0,1 s después de la publicación.

### Validación y calidad de la señal

`fuente_ecg.py` reúne todos los problemas antes de rechazar un archivo y los informa
con su número de línea:

- **Error (la señal no se usa):** archivo inexistente, no seleccionado, vacío o sin
  encabezado; columnas obligatorias ausentes; celdas vacías, no numéricas o no finitas;
  menos de dos muestras; tiempos negativos, repetidos o desordenados; FC fuera de 20 a
  240 latido/min; eficiencia fuera de 0,2 a 1,2.
- **Advertencia (la señal queda `degradado`, pero se puede simular):** evento
  desconocido, muestreo irregular o posible pérdida de muestras.

Ante un error la aplicación no se cierra. La interfaz muestra los mensajes, descarta la
señal y borra los resultados anteriores para que no se confundan con los del archivo
nuevo.

## Pruebas

```bash
python3 -m unittest discover -s pruebas -t . -v
```

Se ejecutan 43 pruebas: las 25 originales de `test_paciente_virtual.py`, sin cambios, y
18 nuevas. Las cinco que exige la letra están en `pruebas/test_agente_ecg.py`:

| Prueba | Qué verifica |
|---|---|
| `test_lee_y_valida_un_csv_correcto` | Columnas, conversión, 5001 muestras, 250 Hz, calidad y episodios. |
| `test_rechaza_un_csv_incorrecto` | Columnas ausentes, vacíos, texto, rangos, menos de dos muestras y archivos inexistentes. |
| `test_rechaza_tiempos_repetidos_o_desordenados` | Tiempos no negativos y estrictamente crecientes. |
| `test_publica_la_muestra_correspondiente_al_tiempo` | Nombres y unidades, promedio del intervalo, distintos pasos, sin pérdida ni duplicación y registro en el motor. |
| `test_la_arritmia_modifica_el_paciente_y_luego_se_recupera` | Cambios de FC, VS, GC, PAM y DO₂ durante el episodio y recuperación posterior. |

Las demás prueban otra fuente distinta del CSV, un episodio en otros tiempos, el
análisis por fases, los CSV de `datos_prueba/` y las rutas de la interfaz sin abrir el
navegador (`pruebas/test_interfaz_ecg.py`).

## Archivos nuevos y modificados

| Archivo | Cambio |
|---|---|
| `src/paciente_virtual/fuente_ecg.py` | **Nuevo.** Lectura y validación (`leer_csv_ecg`, `interpretar_csv_ecg`, `validar_muestras`), `SenalECG` y calidad. |
| `src/paciente_virtual/ecg.py` | **Nuevo.** `AgenteECG`, contrato `FuenteMuestrasECG` y estrategia de sincronización. |
| `src/paciente_virtual/configuracion.py` | Parámetro opcional `agentes_adicionales`; sin él, el motor es idéntico al original. |
| `src/paciente_virtual/analisis.py` | Nueva función `analizar_por_fases` (antes, durante y después de un intervalo). |
| `interfaz_web.py` | Ruta `POST /ecg/cargar`, envío de la señal a `/simular` y `/sensibilidad`, sección y gráfica del ECG, marcadores del episodio y tabla por fases. |
| `ejecutar_simulacion_ecg.py` | **Nuevo.** Simulación acoplada sin interfaz. |
| `pruebas/test_agente_ecg.py`, `pruebas/test_interfaz_ecg.py` | **Nuevos.** Pruebas del agente, la validación y la interfaz. |
| `datos_prueba/` | **Nuevo.** CSV de prueba y el script que los genera. |
| `informe/` | **Nuevo.** Informe y generación reproducible de sus datos y figuras. |

El motor, el estado, los tres agentes fisiológicos y el catálogo de variables no se
modificaron.

## Reemplazar el CSV por otra fuente

1. Escribir una clase que cumpla `FuenteMuestrasECG` (`ecg.py`): `calidad`,
   `tiempo_final_s`, `muestras_en_intervalo(inicio_s, fin_s)` y
   `ultima_muestra_hasta(tiempo_s)`.
2. Si la fuente produce `MuestraECG`, validarlas con
   `fuente_ecg.validar_muestras(muestras, origen)` para reutilizar los mismos controles.
3. Registrar el agente con `crear_motor_referencia(agentes_adicionales=[AgenteECG(fuente)])`.

Para una fuente en vivo (microcontrolador, Raspberry Pi, red o IA), la clase guardaría
las muestras con su tiempo en un búfer acotado. Como la sincronización solo usa muestras
del pasado, el agente funciona igual. Una salida de IA con poca confianza se publicaría
con calidad `degradado`.

## Modelo fisiológico base (código entregado)

- **Cardiovascular:** calcula FC, VS, GC, PAM y DO₂. La FC tiende a su objetivo con
  τ = 3 s y la PAM con τ = 2 s. Si `frecuencia_cardiaca_objetivo > 0`, esa entrada
  reemplaza el objetivo autonómico de la FC; `eficiencia_ritmo` multiplica
  directamente el VS. Es un modelo concentrado: no representa cavidades, válvulas ni
  pulsatilidad.
- **Nervioso:** barorreflejo y quimiorreflejo reducidos. La caída de la PAM aumenta la
  actividad simpática y reduce la parasimpática, con constantes de tiempo distintas.
- **Respiratorio:** ventilación, PaCO₂ con un compartimento dinámico, ecuación alveolar
  simplificada, saturación por curva de Hill, contenido arterial de O₂ y pH estimado.

Los escenarios originales (`ejecutar_simulacion.py`, `ejecutar_escenarios.py`) siguen
funcionando igual. Las ecuaciones y sus fuentes están en el manual de diseño del curso.
