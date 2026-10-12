import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
VERSION_INTERFAZ = "1.4.0-ecg"

from paciente_virtual.escenarios import ESCENARIOS
from paciente_virtual.configuracion import crear_motor_referencia
from paciente_virtual.motor import EventoPerturbacion
from paciente_virtual.analisis import analizar_historial, analizar_por_fases
from paciente_virtual.ecg import AgenteECG
from paciente_virtual.fuente_ecg import ErrorSenalECG, SenalECG, interpretar_csv_ecg

LIMITE_ECG_BYTES = 20 * 1024 * 1024
EVENTO_BASAL_ECG = "ritmo_basal"
MARGEN_RECUPERACION_S = 20.0
FRASE_SIN_PERTURBACIONES = "Ejecución basal sin perturbaciones."

VARIABLES = {
    "frecuencia_cardiaca": "Frecuencia cardiaca (latido/min)",
    "presion_arterial_media": "Presion arterial media (mmHg)",
    "gasto_cardiaco": "Gasto cardiaco (L/min)",
    "contenido_arterial_o2": "Contenido arterial de O2 (mL/dL)",
    "aporte_sistemico_o2": "Aporte sistemico de O2 (mL/min)",
    "presion_arterial_co2": "PaCO2 (mmHg)",
    "presion_arterial_o2": "PaO2 (mmHg)",
    "saturacion_arterial_o2": "SaO2 (%)",
    "ph_arterial": "pH arterial estimado",
    "frecuencia_respiratoria": "Frecuencia respiratoria (respiracion/min)",
    "actividad_simpatica": "Actividad simpatica",
    "actividad_parasimpatica": "Actividad parasimpatica",
    "volumen_sistolico": "Volumen sistolico (mL/latido)",
    "frecuencia_cardiaca_objetivo": "Frecuencia cardiaca objetivo ECG (latido/min)",
    "eficiencia_ritmo": "Eficiencia del ritmo ECG (1)",
}


def interpretar_ecg_recibido(datos_ecg) -> SenalECG:
    """Convierte el archivo enviado por el navegador en una señal validada por fuente_ecg."""
    if not isinstance(datos_ecg, dict) or not datos_ecg.get("nombre") or not datos_ecg.get("contenido"):
        raise ErrorSenalECG("sin archivo", ["No se seleccionó ningún archivo"])
    nombre, contenido = str(datos_ecg["nombre"]), str(datos_ecg["contenido"])
    if len(contenido.encode("utf-8")) > LIMITE_ECG_BYTES:
        raise ErrorSenalECG(nombre, [
            f"el archivo supera el tamaño máximo permitido ({LIMITE_ECG_BYTES // (1024 * 1024)} MB)"
        ])
    return interpretar_csv_ecg(contenido, nombre)


def cargar_ecg(datos: dict) -> dict:
    senal = interpretar_ecg_recibido(datos)
    return {
        "resumen": senal.resumen(),
        "muestras": {
            "tiempo_s": list(senal.tiempos_s),
            "ecg_mV": list(senal.amplitudes_mV),
            "evento": [muestra.evento for muestra in senal.muestras],
        },
    }


def simular(datos: dict) -> dict:
    nombre = datos.get("escenario", "basal")
    escenario = ESCENARIOS[nombre]
    eventos = list(escenario.eventos)
    eventos_personalizados = datos.get("eventos_personalizados", [])
    if not eventos_personalizados and datos.get("usar_evento_personalizado"):
        eventos_personalizados = [{
            "variable": datos.get("variable_evento", "volumen_sanguineo"),
            "tiempo_s": datos.get("tiempo_evento_s", 10.0),
            "valor": datos.get("valor_evento", 4.0),
        }]
    tiempos_personalizados = []
    for numero, especificacion in enumerate(eventos_personalizados, start=1):
        variable = str(especificacion["variable"])
        tiempo_evento = float(especificacion["tiempo_s"])
        valor_evento = float(especificacion["valor"])
        duracion_evento = float(especificacion.get("duracion_s", 0.0))
        if tiempo_evento < 0:
            raise ValueError("El tiempo del evento no puede ser negativo")
        if duracion_evento < 0:
            raise ValueError("La duracion de la rampa no puede ser negativa")
        eventos.append(EventoPerturbacion(f"evento_personalizado_{numero}", tiempo_evento, {variable: valor_evento}, duracion_evento))
        tiempos_personalizados.append(tiempo_evento)
    paso_s = float(datos.get("paso_s", 0.1))
    if paso_s <= 0 or paso_s > 1.0:
        raise ValueError("El paso temporal debe ser mayor que 0 y menor o igual que 1 s")
    senal = interpretar_ecg_recibido(datos["ecg"]) if datos.get("ecg") is not None else None
    agentes_ecg = [AgenteECG(senal)] if senal else None
    motor = crear_motor_referencia(paso_s=paso_s, eventos=eventos, agentes_adicionales=agentes_ecg)
    cambios = {
        "volumen_sanguineo": float(datos.get("volumen_sanguineo", 5.0)),
        "resistencia_vascular_sistemica": float(datos.get("resistencia", 18.0)),
        "contractilidad": float(datos.get("contractilidad", 1.0)),
        "factor_ventilatorio": float(datos.get("factor_ventilatorio", 1.0)),
        "hemoglobina": float(datos.get("hemoglobina", 15.0)),
        "bicarbonato": float(datos.get("bicarbonato", 24.0)),
    }
    # Se usan los mismos controles de dominio que para una perturbacion.
    from paciente_virtual.estado import ValorFisiologico
    publicaciones = {}
    for nombre_variable, valor in cambios.items():
        definicion = motor.catalogo[nombre_variable]
        if not definicion.minimo <= valor <= definicion.maximo:
            raise ValueError(f"{nombre_variable} fuera del intervalo permitido")
        publicaciones[nombre_variable] = ValorFisiologico(valor, definicion.unidad, productor="interfaz")
    motor.estado.aplicar_evento(publicaciones)
    duracion = float(datos.get("duracion_s", escenario.duracion_s))
    if not 1.0 <= duracion <= 600.0:
        raise ValueError("La duracion debe estar entre 1 y 600 segundos")
    if any(tiempo > duracion for tiempo in tiempos_personalizados):
        raise ValueError("El evento personalizado ocurre despues de finalizar la simulacion")
    historial = motor.ejecutar(duracion)
    episodios = [e for e in senal.episodios() if e.evento != EVENTO_BASAL_ECG] if senal else []
    marcadores_ecg = []
    for episodio in episodios:
        marcadores_ecg.append({"nombre": f"inicio {episodio.evento}", "tiempo_s": episodio.inicio_s})
        marcadores_ecg.append({"nombre": f"fin {episodio.evento}", "tiempo_s": episodio.fin_s})
    advertencias_simulacion = []
    analisis_ecg = None
    if episodios:
        primero = episodios[0]
        if duracion < primero.fin_s:
            advertencias_simulacion.append(
                f"La duración ({duracion:g} s) no cubre el fin del episodio ({primero.fin_s:g} s): "
                "la arritmia queda incompleta")
        else:
            # Se analiza el historial completo, antes de reducirlo para el navegador.
            analisis_ecg = analizar_por_fases(historial, primero.inicio_s, primero.fin_s)
        if duracion < primero.fin_s + MARGEN_RECUPERACION_S:
            advertencias_simulacion.append(
                "La duración no alcanza para observar la recuperación completa "
                f"(se recomiendan al menos {round(primero.fin_s + MARGEN_RECUPERACION_S)} s)")
    # Reduce el volumen enviado al navegador manteniendo extremos y forma.
    salto = max(1, len(historial) // 1200)
    historial = historial[::salto]
    respuesta = {"historial": historial, "eventos": motor.eventos_aplicados, "variables": VARIABLES}
    respuesta["analisis"] = analizar_historial(historial, motor.eventos_aplicados)
    respuesta["marcadores_ecg"] = marcadores_ecg
    respuesta["advertencias_simulacion"] = advertencias_simulacion
    if senal:
        resumen_senal = senal.resumen()
        if episodios:
            descripcion = f"{episodios[0].evento} de {episodios[0].inicio_s:g} s a {episodios[0].fin_s:g} s"
        else:
            descripcion = "sin episodios distintos del ritmo basal"
        frases = [t for t in respuesta["analisis"]["resumen"] if t != FRASE_SIN_PERTURBACIONES]
        respuesta["analisis"]["resumen"] = [
            f"Señal ECG externa '{senal.origen}' (calidad {resumen_senal['calidad']}): {descripcion}.",
            *frases,
        ]
        respuesta["ecg"] = resumen_senal
        respuesta["analisis_ecg"] = analisis_ecg
    if datos.get("comparar_basal"):
        # La referencia usa el mismo paso que el experimento y no incluye el agente ECG.
        referencia = ESCENARIOS["basal"].crear_motor(paso_s=paso_s).ejecutar(duracion)
        respuesta["historial_referencia"] = referencia[::max(1, len(referencia) // 1200)]
    return respuesta


def analizar_sensibilidad(datos: dict) -> dict:
    pasos = (0.05, 0.10, 0.20, 0.50)
    filas = []
    referencia = None
    claves = ("presion_arterial_media", "frecuencia_cardiaca", "presion_arterial_co2", "aporte_sistemico_o2")
    for paso in pasos:
        configuracion = dict(datos)
        configuracion["paso_s"] = paso
        configuracion["comparar_basal"] = False
        resultado = simular(configuracion)
        metricas = resultado["analisis"]["metricas"]
        valores = {
            "paso_s": paso,
            "pam_minima": metricas["presion_arterial_media"]["minimo"],
            "fc_maxima": metricas["frecuencia_cardiaca"]["maximo"],
            "paco2_maxima": metricas["presion_arterial_co2"]["maximo"],
            "aporte_o2_minimo": metricas["aporte_sistemico_o2"]["minimo"],
        }
        vector = [metricas[k][extremo] for k, extremo in zip(
            claves, ("minimo", "maximo", "maximo", "minimo")
        )]
        if referencia is None:
            referencia = vector
            diferencia = 0.0
        else:
            diferencia = max(abs(actual - base) / max(abs(base), 1e-9) * 100.0
                             for actual, base in zip(vector, referencia))
        valores["diferencia_maxima_porcentaje"] = diferencia
        valores["aceptable"] = diferencia <= 2.0
        filas.append(valores)
    return {"filas": filas, "criterio_porcentaje": 2.0}


HTML = r'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Paciente Virtual 1.4.0-ecg</title><style>
body{font-family:system-ui;margin:0;background:#f3f6f9;color:#172536}header{background:#17365d;color:white;padding:18px 28px}.encabezado{display:flex;justify-content:space-between;align-items:center;gap:24px}.encabezado h1{margin:0 0 5px}.datos-materia{text-align:right;line-height:1.45}.version{display:inline-block;margin-top:7px;padding:3px 9px;border:1px solid #ffffff66;border-radius:12px;font-size:13px}main{display:grid;grid-template-columns:310px 1fr;gap:18px;padding:18px}.panel{background:white;border-radius:10px;padding:18px;box-shadow:0 2px 8px #0001}label{display:block;margin-top:10px;font-size:14px}input,select{width:100%;box-sizing:border-box;padding:8px;margin-top:4px;border:1px solid #aeb9c5;border-radius:5px}button{width:100%;margin-top:10px;padding:11px;background:#17365d;color:white;border:0;border-radius:6px;font-weight:600}.secundario{background:#64778b}.fila-botones{display:grid;grid-template-columns:1fr 1fr;gap:8px}.comparar{display:flex;gap:8px;align-items:center}.comparar input{width:auto}canvas{width:100%;height:260px;border:1px solid #d6dde5;border-radius:6px;cursor:crosshair}.selector{margin-top:12px;max-height:190px;overflow:auto;border:1px solid #d6dde5;padding:7px;border-radius:6px}.selector label{margin:4px 0;display:flex;gap:7px;align-items:center}.selector input{width:auto;margin:0}.graficas{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}.grafica{position:relative;border:1px solid #dce3ea;border-radius:8px;padding:10px}.grafica h3{font-size:15px;margin:0 0 8px}.resumen{font-size:13px;color:#526273;margin-top:5px}.tooltip-grafica{display:none;position:fixed;z-index:20;pointer-events:none;background:#172536;color:white;padding:7px 9px;border-radius:5px;font-size:12px;line-height:1.45;box-shadow:0 2px 8px #0005;white-space:nowrap}#estado{margin-top:12px;font-size:14px}.insignia{display:inline-block;padding:2px 9px;border-radius:10px;color:white;font-size:12px;background:#8293a5}#ecg_mensajes{margin:4px 0 10px}@media(max-width:800px){.encabezado{display:block}.datos-materia{text-align:left;margin-top:12px}main{grid-template-columns:1fr}.graficas{grid-template-columns:1fr}}
</style></head><body><header><div class="encabezado"><div><h1>Paciente Virtual</h1><div>Simulador educativo cardiorrespiratorio</div><span class="version">Versión 1.4.0-ecg</span></div><div class="datos-materia"><strong>Fundamentos de Ingeniería Biomédica</strong><br>Universidad ORT Uruguay<br>Año 2026</div></div></header><main>
<section class="panel"><h2>Configuracion</h2><label>Escenario<select id="escenario"><option>basal</option><option>hemorragia</option><option>aumento_resistencia</option><option>hipoventilacion</option></select></label>
<label>Duracion (s)<input id="duracion_s" type="number" value="60" min="1" max="600"></label>
<label>Volumen sanguineo (L)<input id="volumen_sanguineo" type="number" value="5" step="0.1"></label>
<label>Resistencia vascular (mmHg min/L)<input id="resistencia" type="number" value="18" step="0.5"></label>
<label>Contractilidad relativa<input id="contractilidad" type="number" value="1" step="0.05"></label>
<label>Factor ventilatorio<input id="factor_ventilatorio" type="number" value="1" step="0.05"></label>
<label>Hemoglobina (g/dL)<input id="hemoglobina" type="number" value="15" step="0.1"></label>
<label>Bicarbonato (mmol/L)<input id="bicarbonato" type="number" value="24" step="0.5"></label>
<h3>Perturbaciones personalizadas</h3>
<label>Variable<select id="variable_evento"><option value="volumen_sanguineo">Volumen sanguineo (L)</option><option value="resistencia_vascular_sistemica">Resistencia vascular (mmHg min/L)</option><option value="contractilidad">Contractilidad relativa</option><option value="factor_ventilatorio">Factor ventilatorio</option></select></label>
<div class="fila-botones"><label>Instante (s)<input id="tiempo_evento_s" type="number" value="10" step="0.1"></label><label>Nuevo valor<input id="valor_evento" type="number" value="4" step="0.1"></label></div><label>Duracion de la rampa (s; 0 = cambio instantaneo)<input id="duracion_evento_s" type="number" value="0" min="0" step="0.1"></label><button class="secundario" onclick="agregarEvento()">Agregar evento</button><div id="lista_eventos" class="selector">Sin eventos adicionales.</div>
<label class="comparar"><input id="comparar_basal" type="checkbox">Comparar con paciente basal</label>
<label>Curvas visibles</label><div id="variables" class="selector"></div><button onclick="ejecutar(this)">Ejecutar simulacion</button><button class="secundario" onclick="sensibilidad(this)">Analizar paso temporal</button><div class="fila-botones"><button class="secundario" onclick="restaurar()">Restaurar</button><button class="secundario" onclick="exportar()">Exportar CSV</button></div><div class="fila-botones"><button class="secundario" onclick="exportarExperimento()">Guardar experimento</button><button class="secundario" onclick="document.getElementById('archivo_experimento').click()">Cargar experimento</button></div><input id="archivo_experimento" type="file" accept="application/json,.json" hidden onchange="cargarExperimento(this)"><div id="estado">Listo.</div></section>
<section class="panel"><h2>Resultados temporales</h2><div id="sensibilidad"></div><div id="analisis"></div><div id="graficas" class="graficas"></div></section>
<section class="panel" style="grid-column:1/-1"><h2>Señal de ECG externa</h2>
<p class="resumen">Cargue el CSV generado por <code>agente_externo_ecg.py</code> (u otra fuente con el mismo formato). La señal se valida en el servidor y, al ejecutar la simulación, el agente ECG publica la frecuencia cardíaca objetivo y la eficiencia del ritmo.</p>
<div class="fila-botones" style="max-width:520px"><button class="secundario" onclick="document.getElementById('archivo_ecg').click()">Seleccionar CSV de ECG</button><button class="secundario" onclick="quitarECG()">Quitar señal</button></div>
<input id="archivo_ecg" type="file" accept=".csv,text/csv" hidden onchange="cargarECG(this)">
<p><strong id="ecg_nombre">Sin señal cargada</strong> <span id="ecg_calidad" class="insignia">sin señal</span></p>
<div id="ecg_datos" class="resumen"></div>
<ul id="ecg_mensajes" class="resumen"></ul>
<div class="grafica"><canvas id="lienzo_ecg" width="1000" height="260"></canvas></div>
</section>
</main><script>
let resultado=null;
let eventosPersonalizados=[];
function agregarEvento(){let variable=document.getElementById('variable_evento').value,tiempo_s=Number(document.getElementById('tiempo_evento_s').value),valor=Number(document.getElementById('valor_evento').value),duracion_s=Number(document.getElementById('duracion_evento_s').value);if(!Number.isFinite(tiempo_s)||!Number.isFinite(valor)||!Number.isFinite(duracion_s)){document.getElementById('estado').textContent='Complete tiempo, valor y duracion.';return}eventosPersonalizados.push({variable,tiempo_s,valor,duracion_s});eventosPersonalizados.sort((a,b)=>a.tiempo_s-b.tiempo_s);mostrarEventos()}
function quitarEvento(i){eventosPersonalizados.splice(i,1);mostrarEventos()}
function mostrarEventos(){let z=document.getElementById('lista_eventos');if(!eventosPersonalizados.length){z.textContent='Sin eventos adicionales.';return}z.innerHTML='';eventosPersonalizados.forEach((e,i)=>{let d=document.createElement('div'),tipo=e.duracion_s>0?`rampa de ${e.duracion_s} s`:'instantaneo';d.textContent=`${e.tiempo_s} s · ${e.variable} = ${e.valor} · ${tipo} `;let b=document.createElement('button');b.textContent='Quitar';b.style.cssText='width:auto;padding:3px 7px;margin:3px';b.onclick=()=>quitarEvento(i);d.append(b);z.append(d)})}
async function ejecutar(boton){boton.disabled=true;document.getElementById('estado').textContent='Calculando...';try{let d={};['escenario','duracion_s','volumen_sanguineo','resistencia','contractilidad','factor_ventilatorio','hemoglobina','bicarbonato'].forEach(k=>d[k]=document.getElementById(k).value);d.comparar_basal=document.getElementById('comparar_basal').checked;d.eventos_personalizados=eventosPersonalizados;datosECGParaServidor(d);let r=await fetch('/simular?instante='+Date.now(),{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});let j=await r.json();if(!r.ok){informarErrorSimulacion(j);throw Error(j.error)}resultado=j;if(!document.querySelector('#variables input'))crearSelectores();document.getElementById('graficas').innerHTML='';mostrarAnalisis();requestAnimationFrame(()=>dibujarTodo());informarSimulacion(j)}catch(e){resultado=null;document.getElementById('graficas').innerHTML='';document.getElementById('estado').textContent='Error: '+e.message}finally{boton.disabled=false}}
function mostrarAnalisis(){let z=document.getElementById('analisis'),a=resultado.analisis;z.innerHTML='<h3>Resumen automático</h3>';let ul=document.createElement('ul');a.resumen.forEach(t=>{let li=document.createElement('li');li.textContent=t;ul.append(li)});z.append(ul);let tabla=document.createElement('table');tabla.style.cssText='width:100%;border-collapse:collapse;margin-bottom:16px;font-size:13px';tabla.innerHTML='<tr><th>Variable</th><th>Basal</th><th>Mínimo</th><th>Máximo</th><th>Final</th><th>Recuperación</th></tr>';Object.entries(a.metricas).forEach(([k,m])=>{let tr=document.createElement('tr');tr.innerHTML=`<td>${resultado.variables[k]||k}</td><td>${m.basal.toFixed(2)}</td><td>${m.minimo.toFixed(2)} (${m.tiempo_minimo_s.toFixed(1)} s)</td><td>${m.maximo.toFixed(2)} (${m.tiempo_maximo_s.toFixed(1)} s)</td><td>${m.final.toFixed(2)}</td><td>${m.recuperacion_porcentaje.toFixed(0)} %</td>`;[...tr.children].forEach(c=>c.style.cssText='border-bottom:1px solid #dce3ea;padding:5px;text-align:left');tabla.append(tr)});z.append(tabla);mostrarAnalisisECG(z)}
async function sensibilidad(boton){boton.disabled=true;document.getElementById('estado').textContent='Comparando pasos temporales...';try{let d={};['escenario','duracion_s','volumen_sanguineo','resistencia','contractilidad','factor_ventilatorio','hemoglobina','bicarbonato'].forEach(k=>d[k]=document.getElementById(k).value);d.eventos_personalizados=eventosPersonalizados;datosECGParaServidor(d);let r=await fetch('/sensibilidad?instante='+Date.now(),{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}),j=await r.json();if(!r.ok)throw Error(j.error);let z=document.getElementById('sensibilidad');z.innerHTML='<h3>Sensibilidad al paso temporal</h3>';let t=document.createElement('table');t.style.cssText='width:100%;border-collapse:collapse;margin-bottom:16px;font-size:13px';t.innerHTML='<tr><th>Paso</th><th>PAM mín.</th><th>FC máx.</th><th>PaCO2 máx.</th><th>Aporte O2 mín.</th><th>Diferencia</th><th>Resultado</th></tr>';j.filas.forEach(f=>{let tr=document.createElement('tr');tr.innerHTML=`<td>${f.paso_s.toFixed(2)} s</td><td>${f.pam_minima.toFixed(2)}</td><td>${f.fc_maxima.toFixed(2)}</td><td>${f.paco2_maxima.toFixed(2)}</td><td>${f.aporte_o2_minimo.toFixed(1)}</td><td>${f.diferencia_maxima_porcentaje.toFixed(2)} %</td><td>${f.aceptable?'Aceptable':'Revisar'}</td>`;[...tr.children].forEach(c=>c.style.cssText='border-bottom:1px solid #dce3ea;padding:5px;text-align:left');t.append(tr)});z.append(t);document.getElementById('estado').textContent='Análisis temporal terminado.'}catch(e){document.getElementById('estado').textContent='Error: '+e.message}finally{boton.disabled=false}}
function restaurar(){document.getElementById('escenario').value='basal';document.getElementById('duracion_s').value=60;document.getElementById('volumen_sanguineo').value=5;document.getElementById('resistencia').value=18;document.getElementById('contractilidad').value=1;document.getElementById('factor_ventilatorio').value=1;document.getElementById('hemoglobina').value=15;document.getElementById('bicarbonato').value=24;document.getElementById('variable_evento').value='volumen_sanguineo';document.getElementById('tiempo_evento_s').value=10;document.getElementById('valor_evento').value=4;document.getElementById('comparar_basal').checked=false;eventosPersonalizados=[];resultado=null;mostrarEventos();document.getElementById('graficas').innerHTML='<p>Valores restaurados. Pulse Ejecutar simulacion para generar nuevas curvas.</p>';document.getElementById('estado').textContent='Parametros y graficas restaurados.'}
function exportar(){if(!resultado){document.getElementById('estado').textContent='Primero ejecute una simulacion.';return}let filas=resultado.historial,campos=Object.keys(filas[0]),csv=[campos.join(',')];filas.forEach(f=>csv.push(campos.map(k=>f[k]).join(',')));let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv.join('\n')],{type:'text/csv'}));a.download='paciente_virtual.csv';a.click();URL.revokeObjectURL(a.href)}
function descargarTexto(nombre,texto,tipo){let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([texto],{type:tipo}));a.download=nombre;a.click();URL.revokeObjectURL(a.href)}
function exportarExperimento(){let parametros={};['duracion_s','volumen_sanguineo','resistencia','contractilidad','factor_ventilatorio','hemoglobina','bicarbonato'].forEach(k=>parametros[k]=Number(document.getElementById(k).value));let curvas=[...document.querySelectorAll('#variables input:checked')].map(i=>i.value),experimento={formato:'paciente_virtual_experimento',version_formato:1,version_simulador:'1.0.0',escenario:document.getElementById('escenario').value,parametros,eventos:eventosPersonalizados,comparar_basal:document.getElementById('comparar_basal').checked,curvas};descargarTexto('experimento_paciente_virtual.json',JSON.stringify(experimento,null,2),'application/json');document.getElementById('estado').textContent='Experimento guardado.'}
async function cargarExperimento(input){try{let archivo=input.files[0];if(!archivo)return;let e=JSON.parse(await archivo.text());if(e.formato!=='paciente_virtual_experimento'||e.version_formato!==1)throw Error('Formato de experimento no compatible');if(!['basal','hemorragia','aumento_resistencia','hipoventilacion'].includes(e.escenario))throw Error('Escenario no reconocido');document.getElementById('escenario').value=e.escenario;let permitidos=['duracion_s','volumen_sanguineo','resistencia','contractilidad','factor_ventilatorio','hemoglobina','bicarbonato'];permitidos.forEach(k=>{if(Number.isFinite(Number(e.parametros?.[k])))document.getElementById(k).value=e.parametros[k]});eventosPersonalizados=Array.isArray(e.eventos)?e.eventos.filter(x=>x&&typeof x.variable==='string'&&Number.isFinite(Number(x.tiempo_s))&&Number.isFinite(Number(x.valor))&&Number.isFinite(Number(x.duracion_s||0))).map(x=>({variable:x.variable,tiempo_s:Number(x.tiempo_s),valor:Number(x.valor),duracion_s:Number(x.duracion_s||0)})):[];document.getElementById('comparar_basal').checked=Boolean(e.comparar_basal);mostrarEventos();if(Array.isArray(e.curvas)){document.querySelectorAll('#variables input').forEach(i=>i.checked=e.curvas.includes(i.value))}resultado=null;document.getElementById('graficas').innerHTML='<p>Experimento cargado. Pulse Ejecutar simulacion para calcular las curvas.</p>';document.getElementById('analisis').innerHTML='';document.getElementById('sensibilidad').innerHTML='';document.getElementById('estado').textContent='Experimento cargado; todavía no fue ejecutado.'}catch(error){document.getElementById('estado').textContent='Error al cargar: '+error.message}finally{input.value=''}}
function crearSelectores(){let caja=document.getElementById('variables'),pred=['frecuencia_cardiaca','volumen_sistolico','gasto_cardiaco','presion_arterial_media','aporte_sistemico_o2'];Object.entries(resultado.variables).forEach(([k,v])=>{let l=document.createElement('label'),i=document.createElement('input');i.type='checkbox';i.value=k;i.checked=pred.includes(k);i.onchange=dibujarTodo;l.append(i,document.createTextNode(v));caja.append(l)})}
function dibujarTodo(){if(!resultado)return;let ks=[...document.querySelectorAll('#variables input:checked')].map(i=>i.value),zona=document.getElementById('graficas');zona.innerHTML='';ks.forEach(k=>{let tarjeta=document.createElement('div');tarjeta.className='grafica';let titulo=document.createElement('h3'),canvas=document.createElement('canvas'),res=document.createElement('div');canvas.width=700;canvas.height=300;res.className='resumen';titulo.textContent=resultado.variables[k];tarjeta.append(titulo,canvas,res);zona.append(tarjeta);dibujar(canvas,res,k);activarTooltipFisiologico(canvas,k)})}
function dibujar(c,res,k){let datos=resultado.historial,ref=resultado.historial_referencia||[],x=c.getContext('2d'),w=c.width,h=c.height,m=45,ys=datos.map(d=>d[k]),yr=ref.map(d=>d[k]),todos=ys.concat(yr),ts=datos.map(d=>d.tiempo_s),ymin=Math.min(...todos),ymax=Math.max(...todos);x.clearRect(0,0,w,h);if(ymax==ymin){ymin-=1;ymax+=1}let margen=(ymax-ymin)*.08;ymin-=margen;ymax+=margen;x.strokeStyle='#d7dee6';for(let i=0;i<=4;i++){let py=m+(h-2*m)*i/4;x.beginPath();x.moveTo(m,py);x.lineTo(w-m,py);x.stroke();x.fillStyle='#526273';x.fillText((ymax-(ymax-ymin)*i/4).toFixed(1),3,py+4)}resultado.eventos.forEach(e=>{let px=m+(w-2*m)*(e.tiempo_s-ts[0])/(ts.at(-1)-ts[0]);x.save();x.setLineDash([5,4]);x.strokeStyle='#d35400';x.beginPath();x.moveTo(px,m);x.lineTo(px,h-m);x.stroke();x.restore();x.fillStyle='#d35400';x.fillText(e.nombre,px+3,m+10)});dibujarMarcadoresECG(x,ts,w,h,m);trazar(x,datos,k,ts,ymin,ymax,w,h,m,'#1677b8',false);if(ref.length){trazar(x,ref,k,ref.map(d=>d.tiempo_s),ymin,ymax,w,h,m,'#8293a5',true);x.fillStyle='#1677b8';x.fillText('Configurado',w-170,18);x.fillStyle='#8293a5';x.fillText('Basal',w-80,18)}x.fillStyle='#526273';x.fillText('0 s',m,h-10);x.fillText(ts.at(-1).toFixed(0)+' s',w-m-25,h-10);x.fillText('Tiempo (s)',w/2-28,h-10);x.save();x.translate(13,h/2+18);x.rotate(-Math.PI/2);x.fillText('Valor',0,0);x.restore();res.textContent=`Inicial ${ys[0].toFixed(2)} · Min ${Math.min(...ys).toFixed(2)} · Max ${Math.max(...ys).toFixed(2)} · Final ${ys.at(-1).toFixed(2)}`}
function trazar(x,datos,k,ts,ymin,ymax,w,h,m,color,punteada){x.save();x.strokeStyle=color;x.lineWidth=2.5;if(punteada)x.setLineDash([7,5]);x.beginPath();datos.forEach((d,i)=>{let px=m+(w-2*m)*(ts[i]-ts[0])/(ts.at(-1)-ts[0]),py=h-m-(h-2*m)*(d[k]-ymin)/(ymax-ymin);i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();x.restore()}
function obtenerTooltip(c){let contenedor=c.parentElement,t=contenedor.querySelector('.tooltip-grafica');if(!t){t=document.createElement('div');t.className='tooltip-grafica';contenedor.append(t)}return t}
function dibujarCruceta(c,px,py,m){let x=c.getContext('2d');x.save();x.setLineDash([6,5]);x.strokeStyle='#263746';x.lineWidth=1.2;x.beginPath();x.moveTo(px,m);x.lineTo(px,c.height-m);x.moveTo(m,py);x.lineTo(c.width-m,py);x.stroke();x.restore();x.beginPath();x.arc(px,py,4,0,Math.PI*2);x.fillStyle='#263746';x.fill()}
function activarTooltipFisiologico(c,k){c.onmousemove=e=>{let r=c.getBoundingClientRect(),m=45,xCanvas=(e.clientX-r.left)*c.width/r.width,fraccion=Math.max(0,Math.min(1,(xCanvas-m)/(c.width-2*m))),datos=resultado.historial,i=Math.round(fraccion*(datos.length-1)),p=datos[i],ref=resultado.historial_referencia||[],todos=datos.map(d=>d[k]).concat(ref.map(d=>d[k])),ymin=Math.min(...todos),ymax=Math.max(...todos);if(ymax===ymin){ymin-=1;ymax+=1}let margen=(ymax-ymin)*.08;ymin-=margen;ymax+=margen;dibujar(c,c.parentElement.querySelector('.resumen'),k);let px=m+(c.width-2*m)*(p.tiempo_s-datos[0].tiempo_s)/(datos.at(-1).tiempo_s-datos[0].tiempo_s),py=c.height-m-(c.height-2*m)*(p[k]-ymin)/(ymax-ymin);dibujarCruceta(c,px,py,m);if(senalECG)dibujarECG({tiempo_s:p.tiempo_s});let t=obtenerTooltip(c);t.innerHTML=`<b>${resultado.variables[k]}</b><br>Tiempo: ${p.tiempo_s.toFixed(2)} s<br>Valor: ${p[k].toFixed(3)}`;t.style.display='block';t.style.left=(e.clientX+12)+'px';t.style.top=(e.clientY+12)+'px'};c.onmouseleave=()=>{dibujar(c,c.parentElement.querySelector('.resumen'),k);obtenerTooltip(c).style.display='none';if(senalECG)dibujarECG()}}
// --- Señal de ECG: transporte y dibujo (la validación la hace el servidor) ---
let senalECG = null;
const COLORES_CALIDAD = {valido: '#2e7d32', degradado: '#c77c00', incorrecto: '#c62828'};
const COLOR_ECG = '#7b3fb0';
const MARGEN_ECG = 60;   // margen mayor que en dibujar() para que entren los valores y la etiqueta del eje Y
const FILAS_ANALISIS_ECG = [
  ['frecuencia_cardiaca', 'FC'], ['volumen_sistolico', 'VS'], ['gasto_cardiaco', 'GC'],
  ['presion_arterial_media', 'PAM'], ['aporte_sistemico_o2', 'DO2'],
  ['actividad_simpatica', 'Simpática'], ['actividad_parasimpatica', 'Parasimpática'],
];

function escaparHTML(texto) {
  return String(texto).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

function mostrarEstado(texto, advertencias) {
  let z = document.getElementById('estado');
  z.textContent = texto;
  if (advertencias && advertencias.length) {
    let ul = document.createElement('ul');
    advertencias.forEach(a => { let li = document.createElement('li'); li.textContent = a; ul.append(li); });
    z.append(ul);
  }
}

function limpiarResultados() {
  resultado = null;
  document.getElementById('graficas').innerHTML = '';
  document.getElementById('analisis').innerHTML = '';
  document.getElementById('sensibilidad').innerHTML = '';
}

function mostrarCalidadECG(calidad) {
  let insignia = document.getElementById('ecg_calidad');
  insignia.textContent = calidad || 'sin señal';
  insignia.style.background = COLORES_CALIDAD[calidad] || '#8293a5';
}

function mostrarMensajesECG(mensajes, sonErrores) {
  let ul = document.getElementById('ecg_mensajes');
  ul.innerHTML = '';
  ul.style.color = sonErrores ? '#c62828' : '#8a5a00';
  (mensajes || []).forEach(t => { let li = document.createElement('li'); li.textContent = t; ul.append(li); });
}

function mostrarDatosECG(r) {
  let episodios = r.episodios.map(e => `${e.evento}: ${e.inicio_s}–${e.fin_s} s`).join('; ');
  document.getElementById('ecg_datos').textContent =
    `Muestras: ${r.cantidad_muestras} · Duración: ${r.duracion_s} s · ` +
    `Muestreo: ${r.frecuencia_muestreo_hz.toFixed(2)} Hz · ` +
    `Amplitud: ${r.amplitud_minima_mV.toFixed(3)} a ${r.amplitud_maxima_mV.toFixed(3)} mV · ` +
    `Episodios: ${episodios || 'ninguno'}`;
}

function limpiarECG() {
  senalECG = null;
  let c = document.getElementById('lienzo_ecg');
  c.getContext('2d').clearRect(0, 0, c.width, c.height);
  obtenerTooltip(c).style.display = 'none';
  document.getElementById('ecg_nombre').textContent = 'Sin señal cargada';
  document.getElementById('ecg_datos').textContent = '';
  mostrarMensajesECG([], false);
  mostrarCalidadECG(null);
}

function mostrarErrorECG(nombre, respuesta) {
  limpiarECG();
  document.getElementById('ecg_nombre').textContent = nombre || 'Sin señal cargada';
  mostrarCalidadECG('incorrecto');
  mostrarMensajesECG(respuesta.errores || [respuesta.error], true);
}

async function cargarECG(input) {
  let archivo = input.files[0];
  try {
    if (!archivo) return;
    let contenido = await archivo.text();
    let r = await fetch('/ecg/cargar?instante=' + Date.now(), {method: 'POST', cache: 'no-store',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nombre: archivo.name, contenido})});
    let j = await r.json();
    if (!r.ok) {
      mostrarErrorECG(archivo.name, j);
      limpiarResultados();
      mostrarEstado('El archivo no es válido; no se usará en la simulación. Los resultados anteriores se borraron.');
      return;
    }
    let habiaResultados = resultado !== null;
    senalECG = {nombre: archivo.name, contenido, resumen: j.resumen, muestras: j.muestras};
    document.getElementById('ecg_nombre').textContent = archivo.name;
    mostrarCalidadECG(j.resumen.calidad);
    mostrarDatosECG(j.resumen);
    mostrarMensajesECG(j.resumen.advertencias, false);
    dibujarECG();
    if (habiaResultados) {
      limpiarResultados();
      mostrarEstado('Señal nueva cargada: ejecute la simulación para ver sus efectos');
    } else {
      mostrarEstado(`Señal ${archivo.name} cargada.`);
    }
  } catch (e) {
    mostrarErrorECG(archivo && archivo.name, {errores: [e.message]});
    limpiarResultados();
    mostrarEstado('El archivo no es válido; no se usará en la simulación. Los resultados anteriores se borraron.');
  } finally {
    input.value = '';
  }
}

function quitarECG() {
  limpiarECG();
  limpiarResultados();
  mostrarEstado('Señal ECG quitada; las simulaciones se ejecutarán sin señal ECG.');
}

function datosECGParaServidor(d) {
  if (senalECG) d.ecg = {nombre: senalECG.nombre, contenido: senalECG.contenido};
}

function informarSimulacion(j) {
  let origen = j.ecg ? `Simulación con señal ${j.ecg.origen}` : 'Simulación sin señal ECG';
  mostrarEstado(`${origen}. Eventos aplicados: ${j.eventos.length}.`, j.advertencias_simulacion);
}

function informarErrorSimulacion(j) {
  if (j && j.errores) mostrarErrorECG(j.origen, j);
  limpiarResultados();
}

function escalaECG(c) {
  let t = senalECG.muestras.tiempo_s, r = senalECG.resumen, m = MARGEN_ECG, w = c.width, h = c.height;
  let tmin = t[0], tmax = t.at(-1), amin = r.amplitud_minima_mV, amax = r.amplitud_maxima_mV;
  if (tmax === tmin) tmax = tmin + 1;
  if (amax === amin) { amin -= 1; amax += 1; }
  let margen = (amax - amin) * .08;
  amin -= margen; amax += margen;
  return {
    m, tmin, tmax, amin, amax,
    px: tt => m + (w - 2 * m) * (tt - tmin) / (tmax - tmin),
    py: v => h - m - (h - 2 * m) * (v - amin) / (amax - amin),
    tiempo: px => tmin + (px - m) / (w - 2 * m) * (tmax - tmin),
  };
}

function lineaVertical(x, px, desde, hasta, color) {
  x.save(); x.setLineDash([5, 4]); x.strokeStyle = color;
  x.beginPath(); x.moveTo(px, desde); x.lineTo(px, hasta); x.stroke(); x.restore();
}

function dibujarECG(cursor) {
  let c = document.getElementById('lienzo_ecg'), x = c.getContext('2d'), w = c.width, h = c.height;
  x.clearRect(0, 0, w, h);
  if (!senalECG) return;
  let e = escalaECG(c), m = e.m, t = senalECG.muestras.tiempo_s, a = senalECG.muestras.ecg_mV;
  // Tramos con evento distinto del ritmo basal, sombreados y con sus bordes.
  senalECG.resumen.episodios.filter(p => p.evento !== 'ritmo_basal').forEach(p => {
    let x0 = e.px(p.inicio_s), x1 = e.px(p.fin_s);
    x.fillStyle = 'rgba(123,63,176,0.08)';
    x.fillRect(x0, m, x1 - x0, h - 2 * m);
    [[x0, 'inicio ' + p.evento], [x1, 'fin ' + p.evento]].forEach(([px, nombre]) => {
      lineaVertical(x, px, m, h - m, COLOR_ECG);
      x.fillStyle = COLOR_ECG; x.fillText(nombre, px + 3, m - 6);
    });
  });
  // Grilla y valores de los ejes.
  x.strokeStyle = '#d7dee6'; x.fillStyle = '#526273';
  for (let i = 0; i <= 4; i++) {
    let py = m + (h - 2 * m) * i / 4;
    x.beginPath(); x.moveTo(m, py); x.lineTo(w - m, py); x.stroke();
    x.save(); x.textAlign = 'right';
    x.fillText((e.amax - (e.amax - e.amin) * i / 4).toFixed(2), m - 6, py + 4);
    x.restore();
  }
  let duracion = e.tmax - e.tmin;
  let paso = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500].find(s => duracion / s <= 12) || 1000;
  for (let tt = Math.ceil(e.tmin / paso) * paso; tt <= e.tmax + 1e-9; tt += paso) {
    let px = e.px(tt);
    x.strokeStyle = '#d7dee6'; x.beginPath(); x.moveTo(px, m); x.lineTo(px, h - m); x.stroke();
    x.fillStyle = '#526273'; x.fillText(tt.toFixed(paso < 1 ? 1 : 0), px - 6, h - m + 14);
  }
  x.fillText('Tiempo (s)', w / 2 - 28, h - 8);
  x.save(); x.translate(14, h / 2); x.rotate(-Math.PI / 2); x.textAlign = 'center'; x.fillText('Amplitud (mV)', 0, 0); x.restore();
  // Todas las muestras, sin decimar, con el eje X en tiempo.
  x.save(); x.strokeStyle = '#b03a2e'; x.lineWidth = 1.2; x.beginPath();
  for (let i = 0; i < t.length; i++) { let px = e.px(t[i]), py = e.py(a[i]); i ? x.lineTo(px, py) : x.moveTo(px, py); }
  x.stroke(); x.restore();
  if (cursor && Number.isFinite(cursor.tiempo_s) && cursor.tiempo_s >= e.tmin && cursor.tiempo_s <= e.tmax) {
    lineaVertical(x, e.px(cursor.tiempo_s), m, h - m, '#263746');
  }
}

function muestraMasCercana(tiempos, objetivo) {
  let lo = 0, hi = tiempos.length - 1;
  while (hi - lo > 1) {
    let medio = (lo + hi) >> 1;
    if (tiempos[medio] <= objetivo) lo = medio; else hi = medio;
  }
  return Math.abs(tiempos[hi] - objetivo) < Math.abs(tiempos[lo] - objetivo) ? hi : lo;
}

function activarTooltipECG() {
  let c = document.getElementById('lienzo_ecg');
  c.onmousemove = ev => {
    if (!senalECG) return;
    let r = c.getBoundingClientRect(), e = escalaECG(c), xCanvas = (ev.clientX - r.left) * c.width / r.width;
    let t = senalECG.muestras.tiempo_s, i = muestraMasCercana(t, e.tiempo(xCanvas)), v = senalECG.muestras.ecg_mV[i];
    dibujarECG();
    dibujarCruceta(c, e.px(t[i]), e.py(v), e.m);
    let tip = obtenerTooltip(c);
    tip.innerHTML = `Tiempo: ${t[i].toFixed(3)} s<br>Amplitud: ${v.toFixed(3)} mV<br>Evento: ${escaparHTML(senalECG.muestras.evento[i])}`;
    tip.style.display = 'block'; tip.style.left = (ev.clientX + 12) + 'px'; tip.style.top = (ev.clientY + 12) + 'px';
  };
  c.onmouseleave = () => { dibujarECG(); obtenerTooltip(c).style.display = 'none'; };
}

function dibujarMarcadoresECG(x, ts, w, h, m) {
  // Cada etiqueta baja de renglón si se superpondría con una anterior.
  let finesPorRenglon = [];
  (resultado.marcadores_ecg || []).forEach(e => {
    let px = m + (w - 2 * m) * (e.tiempo_s - ts[0]) / (ts.at(-1) - ts[0]);
    lineaVertical(x, px, m, h - m, COLOR_ECG);
    let ancho = x.measureText(e.nombre).width, inicio = px + 3;
    if (inicio + ancho > w - m) inicio = px - 3 - ancho;
    let renglon = finesPorRenglon.findIndex(fin => inicio > fin + 16);
    if (renglon < 0) renglon = finesPorRenglon.length;
    finesPorRenglon[renglon] = inicio + ancho;
    x.fillStyle = COLOR_ECG; x.fillText(e.nombre, inicio, m + 22 + 12 * renglon);
  });
}

function mostrarAnalisisECG(z) {
  let a = resultado.analisis_ecg, marcas = resultado.marcadores_ecg || [];
  if (!a || marcas.length < 2) return;
  let n = (v, d = 2) => (v === null || v === undefined) ? '—' : v.toFixed(d);
  let h3 = document.createElement('h3');
  h3.textContent = `Análisis por fases (episodio ${n(marcas[0].tiempo_s, 1)}–${n(marcas[1].tiempo_s, 1)} s)`;
  let tabla = document.createElement('table');
  tabla.style.cssText = 'width:100%;border-collapse:collapse;margin-bottom:16px;font-size:13px';
  tabla.innerHTML = '<tr><th>Variable</th><th>Basal</th><th>Inicio del cambio (s)</th><th>Mínimo durante</th>' +
    '<th>Máximo durante</th><th>Fin del episodio</th><th>Final</th><th>Recuperación</th></tr>';
  FILAS_ANALISIS_ECG.forEach(([k, etiqueta]) => {
    let f = a[k];
    if (!f) return;
    let tr = document.createElement('tr');
    tr.innerHTML = `<td>${etiqueta}</td><td>${n(f.basal)}</td><td>${n(f.tiempo_inicio_cambio_s, 1)}</td>` +
      `<td>${n(f.durante.minimo)} @ ${n(f.durante.tiempo_minimo_s, 1)} s</td>` +
      `<td>${n(f.durante.maximo)} @ ${n(f.durante.tiempo_maximo_s, 1)} s</td>` +
      `<td>${n(f.valor_fin_episodio)}</td><td>${n(f.final)}</td>` +
      `<td>${f.tiempo_recuperacion_s === null ? 'no alcanzada' : n(f.tiempo_recuperacion_s, 1) + ' s'}</td>`;
    [...tr.children].forEach(c => c.style.cssText = 'border-bottom:1px solid #dce3ea;padding:5px;text-align:left');
    tabla.append(tr);
  });
  z.append(h3, tabla);
}

activarTooltipECG();
</script></body></html>'''


class Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path != "/":
            self.send_error(404); return
        self._responder(200, "text/html; charset=utf-8", HTML.encode())

    def do_POST(self):
        ruta = urlparse(self.path).path
        if ruta not in {"/simular", "/sensibilidad", "/ecg/cargar"}:
            self.send_error(404); return
        try:
            largo = int(self.headers.get("Content-Length", "0"))
            datos = json.loads(self.rfile.read(largo))
            if ruta == "/ecg/cargar":
                resultado = cargar_ecg(datos)
            else:
                resultado = simular(datos) if ruta == "/simular" else analizar_sensibilidad(datos)
            self._responder(200, "application/json", json.dumps(resultado).encode())
        except ErrorSenalECG as error:
            self._responder(400, "application/json", json.dumps({
                "error": str(error), "calidad": "incorrecto",
                "origen": error.origen, "errores": list(error.errores),
            }).encode())
        except Exception as error:
            self._responder(400, "application/json", json.dumps({"error": str(error)}).encode())

    def _responder(self, codigo, tipo, contenido):
        self.send_response(codigo); self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(contenido))); self.end_headers(); self.wfile.write(contenido)

    def log_message(self, formato, *args):
        pass


def main():
    direccion = "http://127.0.0.1:8765"
    servidor = ThreadingHTTPServer(("127.0.0.1", 8765), Manejador)
    print(f"Paciente Virtual - interfaz {VERSION_INTERFAZ}")
    print(f"Interfaz disponible en {direccion}")
    print("Para cerrar, presione Control+C en esta ventana.")
    threading.Timer(0.7, lambda: webbrowser.open(direccion)).start()
    servidor.serve_forever()


if __name__ == "__main__":
    main()
