# Paciente Virtual

Prototipo educativo que integra tres agentes simplificados: cardiovascular,
respiratorio y nervioso. El objetivo inicial es verificar la arquitectura y el
intercambio de variables; no representa todavía un modelo fisiológico validado.

La carpeta debe conservarse completa: `ejecutar_simulacion.py`, `src` y
`pruebas` deben quedar al mismo nivel. Ejecutar desde la raíz del proyecto:

```bash
python3 ejecutar_simulacion.py
```

Ejecutar pruebas:

```bash
python3 -m unittest discover -s pruebas -t . -v
```

Para ejecutar todos los escenarios incluidos:

```bash
python3 ejecutar_escenarios.py
```

Para abrir la interfaz gráfica local en el navegador:

```bash
python3 interfaz_web.py
```

## Tarea: integración de un agente externo de ECG

Esta entrega no contiene la solución. El programa `agente_externo_ecg.py`
representa una fuente externa que genera la señal entregada.
Los estudiantes deberán desarrollar el agente integrador y agregar su
visualización a la interfaz, respetando el contrato descrito en
`CONTRATO_ECG.md`.

Para generar el CSV de demostración:

```bash
python3 agente_externo_ecg.py
```

El archivo resultante contiene un ritmo basal, una taquiarritmia entre los
segundos 5 y 14 y una recuperación. La interfaz entregada todavía no sabe
leerlo ni graficarlo: esa es parte de la tarea.

También se puede cambiar la señal generada:

```bash
python3 agente_externo_ecg.py --duracion 30 --inicio-arritmia 8 --fin-arritmia 20
```

El agente desarrollado deberá comunicar al modelo las entradas ya preparadas
`frecuencia_cardiaca_objetivo` y `eficiencia_ritmo`. Consulte
`CONTRATO_ECG.md` para conocer el alcance y el informe solicitado.

La simulación escribe `resultados/simulacion.csv`.

## Modelo respiratorio actual

El agente respiratorio calcula frecuencia respiratoria, ventilación minuto,
ventilación alveolar, PaCO2, PaO2 y SaO2. Usa un compartimento dinámico de CO2,
la forma simplificada de la ecuación alveolar del oxígeno y una curva de Hill
para la saturación. Sus parámetros están en `ParametrosRespiratorios` y pueden
reemplazarse sin cambiar el motor.

Es un modelo educativo reducido: supone volumen corriente, espacio muerto,
producción de CO2, cociente respiratorio y gradiente alveolo-arterial constantes.
No debe utilizarse para decisiones clínicas.

## Modelo cardiovascular actual

El agente cardiovascular calcula frecuencia cardíaca, volumen sistólico, gasto
cardíaco y presión arterial media. Relaciona el volumen sanguíneo con la
precarga, la contractilidad con el volumen sistólico y la resistencia vascular
con la poscarga y la presión. También admite estimulación simpática e hipoxia.
Es un modelo concentrado educativo; no representa cavidades, válvulas ni la
forma de onda pulsátil.

## Modelo nervioso actual

El agente nervioso integra un barorreflejo y un quimiorreflejo reducidos. La
presión arterial modifica por vías opuestas las actividades simpática y
parasimpática. El CO2 elevado y el O2 bajo aumentan el impulso respiratorio y
aportan activación simpática. Cada rama tiene una constante de tiempo distinta,
por lo que las respuestas no aparecen instantáneamente.

El acoplamiento de transporte calcula además contenido arterial de oxígeno,
aporte sistémico de oxígeno y pH estimado. Hemoglobina y bicarbonato pueden
modificarse desde la interfaz para explorar sus efectos.

Las instrucciones de instalación y ejecución de la solución del agente ECG están en [INSTRUCCIONES.md](INSTRUCCIONES.md).
