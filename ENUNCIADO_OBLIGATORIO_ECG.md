# Obligatorio 1 — Integración de una fuente externa de ECG al Paciente Virtual

> **Materia:** Fundamentos de Ingeniería Biomédica — Facultad de Ingeniería, Universidad ORT Uruguay
> **Fecha:** Setiembre 2026 · **Grupo:** Nocturno
> **Puntaje:** 0 a 20 puntos
> **Entrega:** 14/10/2026 hasta las 21:00 en gestion.ort.edu.uy (un único ZIP/RAR, máx. 40 MB)
> **Defensa:** obligatoria y eliminatoria (se coordina con el docente por Teams)

---

## 1. Introducción

El Paciente Virtual es una plataforma educativa formada por agentes computacionales que representan distintos componentes de un sistema fisiológico.

En esta tarea se incorpora un agente capaz de recibir una señal de ECG generada por una fuente externa. La señal incluye un período de ritmo basal, un episodio de taquiarritmia y una etapa posterior de recuperación.

El trabajo **no** consiste únicamente en mostrar el ECG. El agente debe **comunicar la alteración al Paciente Virtual** para que se observen sus efectos sobre las principales variables cardiovasculares.

La arquitectura debe permitir que, en el futuro, el archivo CSV pueda sustituirse por:

- Un dispositivo de adquisición de ECG.
- Un microcontrolador o una Raspberry Pi.
- Un modelo matemático.
- Un generador basado en inteligencia artificial.
- Otro programa conectado mediante red.

## 2. Objetivo

Desarrollar e integrar un agente externo de ECG que:

1. Lea y valide una señal almacenada en un archivo CSV.
2. Represente el ECG en la interfaz web.
3. Sincronice la señal con el tiempo del Paciente Virtual.
4. Informe al modelo cardiovascular sobre los cambios del ritmo.
5. Permita analizar los efectos de una arritmia sobre el paciente.
6. Mantenga separadas la fuente de datos, la lógica del agente y la interfaz.

## 3. Material entregado (código base)

- Código base del Paciente Virtual.
- Agentes cardiovascular, respiratorio y nervioso.
- Motor de simulación.
- Interfaz web.
- Pruebas del sistema base (`test_paciente_virtual.py`, 25 pruebas).
- Programa `agente_externo_ecg.py`.
- Archivo `ecg_simulado.csv`.
- Documento `CONTRATO_ECG.md`.

> El código entregado **no** contiene la solución del agente integrador ni la gráfica del ECG.

## 4. Señal de ECG

- Duración: **20 s**
- Frecuencia de muestreo: **250 Hz**

| Intervalo | Estado |
|---|---|
| 0 – 5 s | Ritmo basal |
| 5 – 14 s | Taquiarritmia irregular |
| 14 – 20 s | Retorno al ritmo basal y recuperación |

### Formato del CSV

```csv
tiempo_s,ecg_mV,frecuencia_cardiaca_lpm,eficiencia_ritmo,evento
```

| Columna | Descripción | Unidad |
|---|---|---|
| `tiempo_s` | Tiempo correspondiente a la muestra | s |
| `ecg_mV` | Amplitud de la señal de ECG | mV |
| `frecuencia_cardiaca_lpm` | Frecuencia cardíaca instantánea propuesta | latido/min |
| `eficiencia_ritmo` | Factor simplificado de eficiencia mecánica | sin unidad |
| `evento` | Estado del ritmo | — |

Valores posibles de `evento`:

- `ritmo_basal`
- `taquiarritmia`

> Los valores de frecuencia cardíaca y eficiencia **ya vienen en el archivo**. No se pide obtenerlos a partir de la forma de onda del ECG.

## 5. Trabajo solicitado

Desarrollar un **agente integrador de ECG**.

- Módulo sugerido: `src/paciente_virtual/ecg.py`
- Clase sugerida: `AgenteECG`

(Los nombres pueden cambiarse si se justifica.)

El agente debe:

- Leer los datos generados por la fuente externa.
- Validar la estructura y el contenido del archivo.
- Mantener las muestras ordenadas temporalmente.
- Seleccionar la muestra correspondiente al tiempo actual del motor.
- Publicar las variables requeridas.
- Informar los errores de forma comprensible.
- Poder probarse **sin** ejecutar la interfaz gráfica.

## 6. Integración con el Paciente Virtual

El código base ya dispone de estas entradas (reconocidas por el agente cardiovascular):

```
frecuencia_cardiaca_objetivo
eficiencia_ritmo
```

Correspondencia que debe realizar el agente:

```
frecuencia_cardiaca_lpm  →  frecuencia_cardiaca_objetivo
eficiencia_ritmo         →  eficiencia_ritmo
```

| Variable publicada | Unidad |
|---|---|
| `frecuencia_cardiaca_objetivo` | `latido/min` |
| `eficiencia_ritmo` | `1` |

- **No** es necesario modificar las ecuaciones cardiovasculares entregadas.
- El agente debe **incorporarse al motor** para publicar sus valores durante la simulación. No alcanza con leer el archivo al finalizar ni con mostrarlo directamente en la interfaz.

## 7. Sincronización temporal

El ECG está muestreado a 250 Hz; el motor fisiológico usa un paso temporal más lento. Se debe **implementar y documentar** una estrategia para seleccionar la muestra de cada ciclo del motor.

Estrategias aceptadas (ejemplos):

- La muestra inmediatamente anterior.
- La muestra temporalmente más cercana.
- Un promedio de las muestras comprendidas dentro del ciclo.

No es necesario ejecutar el motor a 250 Hz.

La estrategia elegida debe:

- Respetar el orden temporal.
- Funcionar cuando el paso del motor sea distinto al del ECG.
- Definir qué sucede cuando se terminan las muestras.
- Evitar la pérdida o duplicación incorrecta de información.

## 8. Modificación de la interfaz

La interfaz debe incorporar una **sección de ECG** que permita:

1. Seleccionar un archivo CSV.
2. Cargar y validar la señal.
3. Mostrar el nombre del archivo.
4. Mostrar la calidad general de los datos.
5. Graficar la amplitud del ECG en función del tiempo.
6. Ejecutar la simulación utilizando la señal cargada.
7. Reemplazar el archivo sin reiniciar la aplicación.
8. Actualizar correctamente todas las gráficas.

Información mínima a mostrar:

- Cantidad de muestras.
- Duración de la señal.
- Frecuencia de muestreo **calculada a partir de los intervalos temporales del archivo**.
- Amplitud mínima y máxima.
- Estado de calidad.

La gráfica del ECG debe indicar:

- Tiempo en segundos.
- Amplitud en milivoltios.
- Tiempo y valor bajo el puntero del mouse.
- Una referencia visual de la muestra seleccionada.

Comportamiento recomendado (igual que las gráficas existentes):

- Cuadro con tiempo y valor.
- Línea vertical punteada.
- Línea horizontal punteada.
- Un único indicador que siga al puntero.
- Eliminación del indicador al retirar el mouse.

## 9. Efecto esperado sobre el paciente

Al presionar **Ejecutar simulación** con el agente integrado deben observarse tres etapas:

**Antes de la arritmia:** valores próximos al estado basal.

**Durante la arritmia:** la fuente propone una frecuencia cardíaca elevada y variable y una reducción de la eficiencia del ritmo. La respuesta puede aparecer suavizada por las constantes de tiempo del modelo. Deben producirse cambios en:

- Frecuencia cardíaca.
- Volumen sistólico.
- Gasto cardíaco.
- Presión arterial media.
- Aporte sistémico de oxígeno.

No se exige coincidir exactamente con una implementación de referencia, pero sí cambios coherentes con las entradas y con las ecuaciones del modelo.

**Después de la arritmia:** las entradas vuelven a sus valores basales y las variables comienzan a recuperarse. La recuperación puede no ser instantánea por:

- Las constantes de tiempo del modelo.
- El estado acumulado durante el episodio.
- La respuesta del agente nervioso.
- El acoplamiento entre agentes.

## 10. Validación de datos

El agente debe detectar, como mínimo:

- Archivo inexistente o no seleccionado.
- Columnas obligatorias ausentes.
- Valores vacíos.
- Valores no numéricos.
- Menos de dos muestras.
- Tiempos repetidos.
- Tiempos desordenados.
- Frecuencia cardíaca fuera del intervalo permitido.
- Eficiencia fuera del intervalo permitido.

Ante un error:

- La aplicación **no** debe finalizar abruptamente.
- La señal incorrecta **no** debe incorporarse a la simulación.
- La interfaz debe mostrar un mensaje comprensible.
- Las gráficas anteriores **no** deben presentarse como resultados del archivo nuevo.

Rangos sugeridos:

| Campo | Regla |
|---|---|
| `frecuencia_cardiaca_lpm` | entre 20 y 240 latidos/min |
| `eficiencia_ritmo` | entre 0,2 y 1,2 |
| `tiempo_s` | ≥ 0 y estrictamente creciente |
| `ecg_mV` | valor numérico finito |

## 11. Organización esperada (arquitectura)

```
agente_externo_ecg.py
        ↓
Archivo CSV
        ↓
Fuente o lector de ECG
        ↓
Agente integrador de ECG
        ↓
Motor del Paciente Virtual
        ↓
Agente cardiovascular
        ↓
Interfaz y gráficas
```

Reglas de separación:

- La **interfaz no** debe calcular los efectos fisiológicos.
- El **agente cardiovascular no** debe leer directamente el CSV.
- El **lector del archivo no** debe contener código de visualización.

Esta separación permite sustituir luego el CSV por hardware, IA u otra fuente.

## 12. Pruebas mínimas

Mínimo obligatorio de cinco pruebas automáticas (una prueba puede cubrir varios comportamientos; se pueden agregar más):

1. `test_lee_y_valida_un_csv_correcto` — lectura de columnas obligatorias, conversión de datos, cantidad de muestras, frecuencia de muestreo y estado de calidad.
2. `test_rechaza_un_csv_incorrecto` — rechazo de columnas ausentes, valores vacíos o no numéricos, valores fuera de rango y archivos con menos de dos muestras.
3. `test_rechaza_tiempos_repetidos_o_desordenados` — tiempos no negativos y estrictamente crecientes.
4. `test_publica_la_muestra_correspondiente_al_tiempo` — sincronización con el tiempo del motor y publicación de `frecuencia_cardiaca_objetivo` y `eficiencia_ritmo` con sus unidades correctas.
5. `test_la_arritmia_modifica_el_paciente_y_luego_se_recupera` — el episodio produce cambios en las variables cardiovasculares y luego comienza la recuperación.

**Las 25 pruebas de `test_paciente_virtual.py` deben seguir pasando.**

Archivo recomendado: `pruebas/test_agente_ecg.py`

Estructura de referencia:

```python
import unittest

class PruebasAgenteECG(unittest.TestCase):

    def test_lee_un_csv_valido(self):
        """
        Comprueba que el agente pueda leer y convertir correctamente
        las muestras de un archivo CSV válido.
        """
        ...

    def test_rechaza_columnas_incorrectas(self):
        """
        Comprueba que se produzca un error controlado cuando falte
        alguna de las columnas obligatorias.
        """
        ...

    def test_rechaza_tiempos_repetidos_o_desordenados(self):
        """
        Comprueba que los tiempos de las muestras sean estrictamente
        crecientes.
        """
        ...

    def test_publica_las_variables_requeridas(self):
        """
        Comprueba que el agente publique frecuencia_cardiaca_objetivo
        y eficiencia_ritmo con las unidades correspondientes.
        """
        ...

    def test_la_arritmia_modifica_el_paciente(self):
        """
        Comprueba que durante la arritmia cambien las variables
        cardiovasculares y que posteriormente comience la recuperación.
        """
        ...

if __name__ == "__main__":
    unittest.main()
```

Comando para ejecutar todas las pruebas:

```bash
python3 -m unittest discover -s pruebas -t . -v
```

## 13. Informe de resultados (PDF)

### Arquitectura
- Organización del agente desarrollado.
- Separación entre fuente, agente, motor e interfaz.
- Variables consumidas y publicadas.
- Estrategia de sincronización temporal.

### Resultados
Gráficas de: ECG, frecuencia cardíaca, volumen sistólico, gasto cardíaco, presión arterial media y aporte sistémico de oxígeno.

El análisis debe diferenciar: estado previo a la arritmia, comportamiento durante la arritmia y recuperación posterior.

Para cada variable indicar:
- Qué cambió.
- En qué momento comenzó el cambio.
- Valor basal aproximado.
- Valor mínimo o máximo relevante.
- Comportamiento al finalizar el episodio.
- Relación con las entradas del agente y el modelo implementado.

### Discusión
- Por qué graficar el ECG no es suficiente para afectar al Paciente Virtual.
- Cómo se comunica el agente con el modelo cardiovascular.
- Qué simplificaciones tiene el escenario.
- Cómo se podría sustituir el CSV por hardware o IA.
- Qué partes del sistema podrían mantenerse sin cambios.

> No se pide diagnóstico clínico ni clasificación automática de la arritmia.

## 14. Entregables

1. Código fuente completo.
2. Módulo del agente de ECG.
3. Modificaciones realizadas en la interfaz.
4. Pruebas automáticas.
5. Archivos CSV utilizados.
6. Informe técnico en PDF.
7. Instrucciones breves de instalación y ejecución.

La solución debe poder ejecutarse **desde la carpeta principal** con:

```bash
python3 agente_externo_ecg.py
python3 interfaz_web.py
```

Y las pruebas con:

```bash
python3 -m unittest discover -s pruebas -t . -v
```

Se entrega un único ZIP o RAR con código fuente, pruebas, informe PDF e instrucciones.

## 15. Demostración (defensa)

1. Ejecutar el generador externo.
2. Cargar el CSV desde la interfaz.
3. Mostrar el ECG.
4. Ejecutar la simulación acoplada.
5. Identificar el inicio y el final de la arritmia.
6. Explicar los cambios en las principales variables.
7. Cargar un archivo incorrecto y mostrar el manejo del error.
8. Ejecutar las pruebas automáticas.
9. Explicar cómo se reemplazaría el CSV por otra fuente.

## 16. Ayudas y orientaciones

### Estructura del agente

```python
identificador = "agente_ecg"
entradas = frozenset()
salidas = frozenset({
    "frecuencia_cardiaca_objetivo",
    "eficiencia_ritmo",
})
```

### Tiempo actual

```python
estado.tiempo_s
```

### Publicación de variables

Usar el mismo tipo `Publicacion` que los demás agentes:

```python
Publicacion(
    "frecuencia_cardiaca_objetivo",
    valor_frecuencia,
    "latido/min",
)
Publicacion(
    "eficiencia_ritmo",
    valor_eficiencia,
    "1",
)
```

### Incorporación al motor
El agente debe formar parte de la **lista de agentes usada para construir el motor**. Crear el objeto sin registrarlo en el motor no modifica la simulación.

### Diferencias de frecuencia
No es necesario procesar las 250 muestras por ciclo fisiológico. Se puede seleccionar una única muestra representativa para publicar las variables de control y conservar todas las muestras para dibujar el ECG.

### Comprobación rápida
Si el ECG se muestra pero las curvas fisiológicas no cambian, revisar:

- Que el archivo se envíe al ejecutar la simulación.
- Que el agente esté registrado en el motor.
- Que el agente publique sus variables en cada ciclo.
- Que los nombres y las unidades coincidan **exactamente**.
- Que la duración de la simulación incluya los segundos 5 a 14.
- Que no se esté ejecutando una versión anterior del servidor.

### Actualización de las gráficas
Antes de redibujar un lienzo HTML se debe **borrar su contenido anterior**; si no, las curvas o líneas auxiliares se acumulan entre movimientos del mouse o ejecuciones consecutivas.

## 17. Alcance y limitaciones

Proyecto con fines exclusivamente educativos. **No** se solicita:

- Diagnosticar una arritmia.
- Validar clínicamente el ECG.
- Obtener automáticamente la frecuencia a partir de la forma de onda.
- Implementar obligatoriamente hardware o IA.
- Reemplazar los agentes fisiológicos existentes.
- Ejecutar el motor fisiológico a 250 Hz.

Resultado esperado: una integración funcional, comprensible y reutilizable que muestre cómo una señal de un agente externo modifica el comportamiento del Paciente Virtual.

## 18. Criterios de evaluación

Se evalúa el resultado final y el proceso de desarrollo. Se valora especialmente:

- Uso correcto de la arquitectura propuesta.
- Respeto por las interfaces y el protocolo de comunicación.
- Separación entre fuente de datos, agente integrador, motor de simulación e interfaz.
- Independencia de la integración respecto de los agentes fisiológicos entregados.
- Correcta sincronización entre el ECG y el tiempo de simulación.
- Validación y comunicación de la calidad de los datos.
- Reproducibilidad de las simulaciones.
- Calidad de las pruebas automáticas.
- Claridad y coherencia del análisis de resultados.

> Un sistema que solo se ejecute sin errores o que solo grafique el ECG **no será suficiente**. La integración debe modificar efectivamente el comportamiento del Paciente Virtual, y el equipo debe poder explicar por qué se obtienen los resultados observados.

## Uso de IA generativa (condiciones del curso)

- Seguir las pautas de los docentes sobre el uso de IA.
- Citar correctamente las fuentes y la forma en que se usó la IA.
- Verificar el contenido generado por la IA.
- Ser responsables (alucinaciones, privacidad, propiedad intelectual, sesgos, contenido falso).
- Ante dudas de autoría o uso no atribuido de IA, el docente puede convocar a una defensa individual.

---

## Checklist de implementación

- [ ] Lector/fuente de ECG separado (sin código de visualización)
- [ ] `AgenteECG` en `src/paciente_virtual/ecg.py` con `identificador`, `entradas`, `salidas`
- [ ] Validaciones de la sección 10 con mensajes comprensibles
- [ ] Cálculo de calidad: n.º de muestras, duración, fs desde intervalos, min/max, estado
- [ ] Estrategia de sincronización implementada y documentada (incluye fin de muestras)
- [ ] Publicación de `frecuencia_cardiaca_objetivo` (`latido/min`) y `eficiencia_ritmo` (`1`) en cada ciclo
- [ ] Agente registrado en la lista de agentes del motor
- [ ] Sección ECG en la interfaz (selección, carga, info, gráfica con cursor, reemplazo sin reinicio)
- [ ] Limpieza del canvas antes de redibujar
- [ ] `pruebas/test_agente_ecg.py` con las 5 pruebas mínimas
- [ ] Las 25 pruebas de `test_paciente_virtual.py` siguen pasando
- [ ] Informe PDF + instrucciones de ejecución + ZIP final
