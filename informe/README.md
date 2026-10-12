# Informe

| Ruta | Contenido |
|---|---|
| `Informe Obligatorio 1 - FIB.docx` | Informe técnico del obligatorio. |
| `generar_resultados_informe.py` | Ejecuta las simulaciones del informe y guarda los datos en `datos/`. |
| `generar_figuras.py` | Dibuja las figuras a partir de `datos/` y las guarda en `figuras/`. |
| `datos/` | Señal usada, historiales con y sin ECG (60 s), análisis por fases, sensibilidad al paso, selección del agente alrededor de 5, 14 y 20 s, y `metadatos.json` (versión de Python, commit y parámetros). |
| `figuras/` | ECG, variables cardiovasculares, entradas publicadas por el agente, sincronización y barorreflejo. |
| `requirements.txt` | `matplotlib`, que solo hace falta para las figuras: el simulador no lo usa. |

Los números del informe salen de estos archivos. Para regenerarlos, desde la raíz del
proyecto:

```bash
python3 informe/generar_resultados_informe.py
python3 -m pip install -r informe/requirements.txt
python3 informe/generar_figuras.py
```

Condiciones: escenario basal, Δt = 0,1 s, 60 s de simulación y la señal por defecto de
`agente_externo_ecg.py` (20 s, 70 latido/min, taquiarritmia de 5 a 14 s).
