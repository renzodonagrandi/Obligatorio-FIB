# Contrato del agente de ECG

Se proporciona `agente_externo_ecg.py`, que genera un archivo CSV. El
equipo debe desarrollar un agente nuevo que incorpore esa señal al Paciente
Virtual y permita verla en la interfaz web.

## Entrada proporcionada

El archivo CSV contiene una fila por muestra. Entre los segundos 5 y 14 aparece
un episodio simulado de taquiarritmia:

```text
tiempo_s,ecg_mV,frecuencia_cardiaca_lpm,eficiencia_ritmo,evento
0.000,0.012,70.0,1.0,ritmo_basal
0.004,0.018,70.0,1.0,ritmo_basal
```

- `tiempo_s`: instante de la muestra, en segundos.
- `ecg_mV`: amplitud del ECG, en milivoltios.
- `frecuencia_cardiaca_lpm`: frecuencia instantánea que debe comunicarse al
  Paciente Virtual.
- `eficiencia_ritmo`: factor simplificado que reduce el volumen sistólico
  durante la arritmia.
- `evento`: etiqueta educativa (`ritmo_basal` o `taquiarritmia`).

Las dos últimas variables fisiológicas de entrada ya están declaradas en el
Paciente Virtual con estos nombres:

- `frecuencia_cardiaca_objetivo`, en `latido/min`;
- `eficiencia_ritmo`, sin unidad.

El agente que construya el equipo deberá publicar estas variables durante la
simulación. No es necesario modificar las ecuaciones cardiovasculares.

## Salida mínima esperada del agente

El agente desarrollado debe poner a disposición de la interfaz:

- las muestras de tiempo y amplitud;
- el origen de la señal;
- el estado de calidad (`valido`, `degradado` o `incorrecto`);
- la cantidad de muestras;
- la duración de la señal;
- la frecuencia de muestreo estimada.

Debe detectar como mínimo: columnas ausentes, datos no numéricos, menos de dos
muestras y tiempos repetidos o desordenados.

## Informe breve de resultados

El equipo deberá comparar tres intervalos de la simulación:

1. antes de la arritmia;
2. durante la arritmia;
3. después de la arritmia.

El informe deberá incluir las gráficas de ECG y, como mínimo, de:

- frecuencia cardíaca;
- volumen sistólico;
- gasto cardíaco;
- presión arterial media;
- aporte sistémico de oxígeno.

Para cada variable se describirá qué cambió, cuándo comenzó el cambio y si el
valor regresó hacia el nivel inicial. La explicación debe relacionar la señal
recibida con las ecuaciones del modelo. No se solicita diagnóstico clínico ni
identificación automática de la arritmia.

## Condición de reutilización

La lectura de la fuente debe estar separada del agente y de la gráfica. El
diseño debe permitir reemplazar el CSV por hardware, inteligencia artificial u
otro simulador sin reescribir la visualización completa.

Los campos `evento` y `eficiencia_ritmo` se incluyen para mantener la dificultad
centrada en la integración de agentes. No se pide que los estudiantes calculen
estos valores a partir de la forma de onda.
