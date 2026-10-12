# Instrucciones de instalación y ejecución

## Requisitos
- Python 3.10 o posterior (probado con Python 3.12.3). El simulador usa solo la
  biblioteca estándar.
- Un navegador web moderno.
- Opcional, solo para regenerar las figuras del informe: matplotlib
  (`python3 -m pip install -r informe/requirements.txt`).

Comprobar la versión con `python3 --version`. Si es menor que 3.10 (por ejemplo, por
pyenv), crear un entorno virtual con un Python más nuevo:

    python3.12 -m venv .venv
    source .venv/bin/activate

Con el entorno activado, `python3` pasa a ser el Python 3.12 del entorno en todos los
comandos de este documento. En Debian/Ubuntu, si `venv` no está disponible, instalar
antes el paquete `python3.12-venv`.

## Ejecución (desde la carpeta principal)
1. Generar la señal externa: `python3 agente_externo_ecg.py`
   (crea resultados/ecg_simulado.csv).
2. Abrir la interfaz: `python3 interfaz_web.py` (se abre http://127.0.0.1:8765; el
   encabezado debe indicar la versión 1.4.1-ecg).
3. En la sección "Señal de ECG externa", pulsar "Seleccionar CSV de ECG" y elegir
   resultados/ecg_simulado.csv.
4. Pulsar "Ejecutar simulacion" (duración recomendada: 60 s).
5. Para detener el servidor: Control+C. Después de modificar el código hay que
   reiniciarlo.

## Pruebas automáticas
    python3 -m unittest discover -s pruebas -t . -v

Se ejecutan 42 pruebas; todas deben terminar en `OK`.

## Ejecución sin interfaz
    python3 ejecutar_simulacion_ecg.py --csv resultados/ecg_simulado.csv --duracion 60 --paso 0.1

Imprime el resumen de la señal y una tabla por variable (basal, inicio del cambio,
extremo durante el episodio, valor al fin del episodio, final y recuperación). Escribe
el historial en `resultados/simulacion_ecg.csv` (`--salida`) y el análisis por fases en
`resultados/analisis_ecg.json` (`--analisis`).

## Archivos de prueba (datos_prueba/)
| Archivo | Resultado esperado al cargarlo |
|---|---|
| `ecg_valido_20s.csv` | Válido: 20 s, FC 70, taquiarritmia de 5 a 14 s (igual a la señal por defecto). |
| `ecg_valido_30s_arritmia_8_20.csv` | Válido: 30 s, taquiarritmia de 8 a 20 s (el episodio no está fijo). |
| `ecg_degradado_hueco.csv` | Degradado: advertencias de muestreo irregular y de posible pérdida de muestras entre t=10 s y t=10.1 s. Se puede simular. |
| `ecg_invalido_falta_columna.csv` | Error: `línea 1: faltan columnas obligatorias: 'eficiencia_ritmo'`. |
| `ecg_invalido_tiempos.csv` | Error: tiempo repetido en la muestra 5 y tiempos desordenados en la muestra 8. |
| `ecg_invalido_rangos.csv` | Error: `frecuencia_cardiaca_lpm=300` fuera de [20, 240] y `eficiencia_ritmo=0.1` fuera de [0.2, 1.2]. |
| `ecg_invalido_texto.csv` | Error: `'abc' no es un número válido en 'ecg_mV'` y valor vacío en `frecuencia_cardiaca_lpm`. |
| `ecg_invalido_una_muestra.csv` | Error: se necesitan al menos 2 muestras válidas. |

Se regeneran con `python3 datos_prueba/generar_csv_de_prueba.py`.

## Reproducir los resultados del informe
    python3 informe/generar_resultados_informe.py
    python3 informe/generar_figuras.py

El primero deja los datos en `informe/datos/` (incluye `metadatos.json` con la versión
de Python, el commit y los parámetros); el segundo, que requiere matplotlib, deja las
cinco figuras en `informe/figuras/`.

## Problemas frecuentes
- `TypeError: unsupported operand type(s) for |`: se está usando Python < 3.10.
- `Address already in use`: ya hay otro servidor en el puerto 8765; cerrarlo.
- La interfaz muestra otra versión: hay un servidor anterior abierto; reiniciarlo.
- Las curvas no cambian: verificar que la señal esté cargada (insignia "valido") y que
  la duración cubra el episodio (al menos 14 s; 60 s para ver la recuperación).

## Archivos de la solución
- `src/paciente_virtual/fuente_ecg.py` (nuevo): lee el CSV y valida la señal (columnas, números, rangos, tiempos, calidad); `validar_muestras` sirve para cualquier otra fuente.
- `src/paciente_virtual/ecg.py` (nuevo): `AgenteECG`, que publica `frecuencia_cardiaca_objetivo` y `eficiencia_ritmo` a partir de cualquier fuente que cumpla `FuenteMuestrasECG`.
- `src/paciente_virtual/configuracion.py` (modificado): parámetro opcional `agentes_adicionales` para registrar el agente en el motor.
- `src/paciente_virtual/analisis.py` (modificado): `analizar_por_fases`, que compara antes, durante y después de un intervalo.
- `interfaz_web.py` (modificado): ruta `/ecg/cargar`, simulación con la señal, sección y gráfica del ECG, marcadores y tabla por fases. Solo transporta y dibuja.
- `ejecutar_simulacion_ecg.py` (nuevo): simulación y análisis por fases desde la terminal.
- `pruebas/test_agente_ecg.py` (nuevo): pruebas de la lectura, la validación, el agente, el análisis y los CSV de prueba.
- `pruebas/test_interfaz_ecg.py` (nuevo): pruebas del backend de la interfaz sin abrir el servidor.
- `datos_prueba/` (nuevo): CSV válidos, degradado e inválidos, y el script que los genera.
- `informe/` (nuevo): scripts que generan los datos (`informe/datos/`) y las figuras (`informe/figuras/`) del informe.
