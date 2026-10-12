import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
VERSION_INTERFAZ = "1.3.2-estudiantes"

from paciente_virtual.escenarios import ESCENARIOS
from paciente_virtual.configuracion import crear_motor_referencia
from paciente_virtual.motor import EventoPerturbacion
from paciente_virtual.analisis import analizar_historial

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
    motor = crear_motor_referencia(paso_s=paso_s, eventos=eventos)
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
    # Reduce el volumen enviado al navegador manteniendo extremos y forma.
    salto = max(1, len(historial) // 1200)
    historial = historial[::salto]
    respuesta = {"historial": historial, "eventos": motor.eventos_aplicados, "variables": VARIABLES}
    respuesta["analisis"] = analizar_historial(historial, motor.eventos_aplicados)
    if datos.get("comparar_basal"):
        referencia = ESCENARIOS["basal"].crear_motor(paso_s=0.1).ejecutar(duracion)
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
<title>Paciente Virtual 1.3.2 — estudiantes</title><style>
body{font-family:system-ui;margin:0;background:#f3f6f9;color:#172536}header{background:#17365d;color:white;padding:18px 28px}.encabezado{display:flex;justify-content:space-between;align-items:center;gap:24px}.encabezado h1{margin:0 0 5px}.datos-materia{text-align:right;line-height:1.45}.version{display:inline-block;margin-top:7px;padding:3px 9px;border:1px solid #ffffff66;border-radius:12px;font-size:13px}main{display:grid;grid-template-columns:310px 1fr;gap:18px;padding:18px}.panel{background:white;border-radius:10px;padding:18px;box-shadow:0 2px 8px #0001}label{display:block;margin-top:10px;font-size:14px}input,select{width:100%;box-sizing:border-box;padding:8px;margin-top:4px;border:1px solid #aeb9c5;border-radius:5px}button{width:100%;margin-top:10px;padding:11px;background:#17365d;color:white;border:0;border-radius:6px;font-weight:600}.secundario{background:#64778b}.fila-botones{display:grid;grid-template-columns:1fr 1fr;gap:8px}.comparar{display:flex;gap:8px;align-items:center}.comparar input{width:auto}canvas{width:100%;height:260px;border:1px solid #d6dde5;border-radius:6px;cursor:crosshair}.selector{margin-top:12px;max-height:190px;overflow:auto;border:1px solid #d6dde5;padding:7px;border-radius:6px}.selector label{margin:4px 0;display:flex;gap:7px;align-items:center}.selector input{width:auto;margin:0}.graficas{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}.grafica{position:relative;border:1px solid #dce3ea;border-radius:8px;padding:10px}.grafica h3{font-size:15px;margin:0 0 8px}.resumen{font-size:13px;color:#526273;margin-top:5px}.tooltip-grafica{display:none;position:fixed;z-index:20;pointer-events:none;background:#172536;color:white;padding:7px 9px;border-radius:5px;font-size:12px;line-height:1.45;box-shadow:0 2px 8px #0005;white-space:nowrap}#estado{margin-top:12px;font-size:14px}@media(max-width:800px){.encabezado{display:block}.datos-materia{text-align:left;margin-top:12px}main{grid-template-columns:1fr}.graficas{grid-template-columns:1fr}}
</style></head><body><header><div class="encabezado"><div><h1>Paciente Virtual</h1><div>Simulador educativo cardiorrespiratorio</div><span class="version">Versión 1.3.2 — estudiantes</span></div><div class="datos-materia"><strong>Fundamentos de Ingeniería Biomédica</strong><br>Universidad ORT Uruguay<br>Año 2026</div></div></header><main>
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
<section class="panel" style="grid-column:1/-1"><h2>Actividad obligatoria: agente externo de ECG</h2><p><strong>Integración pendiente.</strong> Esta versión no carga ni grafica el ECG. El equipo deberá incorporar el archivo generado por <code>agente_externo_ecg.py</code> y vincularlo con la simulación.</p><p>Para analizar el efecto de la arritmia, la solución deberá mostrar y comparar tres períodos: antes del episodio, durante la taquiarritmia y después de su finalización.</p><p>Curvas mínimas: ECG, frecuencia cardíaca, volumen sistólico, gasto cardíaco, presión arterial media y aporte sistémico de oxígeno.</p></section>
</main><script>
let resultado=null;
let eventosPersonalizados=[];
function agregarEvento(){let variable=document.getElementById('variable_evento').value,tiempo_s=Number(document.getElementById('tiempo_evento_s').value),valor=Number(document.getElementById('valor_evento').value),duracion_s=Number(document.getElementById('duracion_evento_s').value);if(!Number.isFinite(tiempo_s)||!Number.isFinite(valor)||!Number.isFinite(duracion_s)){document.getElementById('estado').textContent='Complete tiempo, valor y duracion.';return}eventosPersonalizados.push({variable,tiempo_s,valor,duracion_s});eventosPersonalizados.sort((a,b)=>a.tiempo_s-b.tiempo_s);mostrarEventos()}
function quitarEvento(i){eventosPersonalizados.splice(i,1);mostrarEventos()}
function mostrarEventos(){let z=document.getElementById('lista_eventos');if(!eventosPersonalizados.length){z.textContent='Sin eventos adicionales.';return}z.innerHTML='';eventosPersonalizados.forEach((e,i)=>{let d=document.createElement('div'),tipo=e.duracion_s>0?`rampa de ${e.duracion_s} s`:'instantaneo';d.textContent=`${e.tiempo_s} s · ${e.variable} = ${e.valor} · ${tipo} `;let b=document.createElement('button');b.textContent='Quitar';b.style.cssText='width:auto;padding:3px 7px;margin:3px';b.onclick=()=>quitarEvento(i);d.append(b);z.append(d)})}
async function ejecutar(boton){boton.disabled=true;document.getElementById('estado').textContent='Calculando...';try{let d={};['escenario','duracion_s','volumen_sanguineo','resistencia','contractilidad','factor_ventilatorio','hemoglobina','bicarbonato'].forEach(k=>d[k]=document.getElementById(k).value);d.comparar_basal=document.getElementById('comparar_basal').checked;d.eventos_personalizados=eventosPersonalizados;let r=await fetch('/simular?instante='+Date.now(),{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});let j=await r.json();if(!r.ok)throw Error(j.error);resultado=j;if(!document.querySelector('#variables input'))crearSelectores();document.getElementById('graficas').innerHTML='';mostrarAnalisis();requestAnimationFrame(()=>dibujarTodo());document.getElementById('estado').textContent=`Simulacion terminada. Eventos aplicados: ${j.eventos.length}.`}catch(e){document.getElementById('estado').textContent='Error: '+e.message}finally{boton.disabled=false}}
function mostrarAnalisis(){let z=document.getElementById('analisis'),a=resultado.analisis;z.innerHTML='<h3>Resumen automático</h3>';let ul=document.createElement('ul');a.resumen.forEach(t=>{let li=document.createElement('li');li.textContent=t;ul.append(li)});z.append(ul);let tabla=document.createElement('table');tabla.style.cssText='width:100%;border-collapse:collapse;margin-bottom:16px;font-size:13px';tabla.innerHTML='<tr><th>Variable</th><th>Basal</th><th>Mínimo</th><th>Máximo</th><th>Final</th><th>Recuperación</th></tr>';Object.entries(a.metricas).forEach(([k,m])=>{let tr=document.createElement('tr');tr.innerHTML=`<td>${resultado.variables[k]||k}</td><td>${m.basal.toFixed(2)}</td><td>${m.minimo.toFixed(2)} (${m.tiempo_minimo_s.toFixed(1)} s)</td><td>${m.maximo.toFixed(2)} (${m.tiempo_maximo_s.toFixed(1)} s)</td><td>${m.final.toFixed(2)}</td><td>${m.recuperacion_porcentaje.toFixed(0)} %</td>`;[...tr.children].forEach(c=>c.style.cssText='border-bottom:1px solid #dce3ea;padding:5px;text-align:left');tabla.append(tr)});z.append(tabla)}
async function sensibilidad(boton){boton.disabled=true;document.getElementById('estado').textContent='Comparando pasos temporales...';try{let d={};['escenario','duracion_s','volumen_sanguineo','resistencia','contractilidad','factor_ventilatorio','hemoglobina','bicarbonato'].forEach(k=>d[k]=document.getElementById(k).value);d.eventos_personalizados=eventosPersonalizados;let r=await fetch('/sensibilidad?instante='+Date.now(),{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}),j=await r.json();if(!r.ok)throw Error(j.error);let z=document.getElementById('sensibilidad');z.innerHTML='<h3>Sensibilidad al paso temporal</h3>';let t=document.createElement('table');t.style.cssText='width:100%;border-collapse:collapse;margin-bottom:16px;font-size:13px';t.innerHTML='<tr><th>Paso</th><th>PAM mín.</th><th>FC máx.</th><th>PaCO2 máx.</th><th>Aporte O2 mín.</th><th>Diferencia</th><th>Resultado</th></tr>';j.filas.forEach(f=>{let tr=document.createElement('tr');tr.innerHTML=`<td>${f.paso_s.toFixed(2)} s</td><td>${f.pam_minima.toFixed(2)}</td><td>${f.fc_maxima.toFixed(2)}</td><td>${f.paco2_maxima.toFixed(2)}</td><td>${f.aporte_o2_minimo.toFixed(1)}</td><td>${f.diferencia_maxima_porcentaje.toFixed(2)} %</td><td>${f.aceptable?'Aceptable':'Revisar'}</td>`;[...tr.children].forEach(c=>c.style.cssText='border-bottom:1px solid #dce3ea;padding:5px;text-align:left');t.append(tr)});z.append(t);document.getElementById('estado').textContent='Análisis temporal terminado.'}catch(e){document.getElementById('estado').textContent='Error: '+e.message}finally{boton.disabled=false}}
function restaurar(){document.getElementById('escenario').value='basal';document.getElementById('duracion_s').value=60;document.getElementById('volumen_sanguineo').value=5;document.getElementById('resistencia').value=18;document.getElementById('contractilidad').value=1;document.getElementById('factor_ventilatorio').value=1;document.getElementById('hemoglobina').value=15;document.getElementById('bicarbonato').value=24;document.getElementById('variable_evento').value='volumen_sanguineo';document.getElementById('tiempo_evento_s').value=10;document.getElementById('valor_evento').value=4;document.getElementById('comparar_basal').checked=false;eventosPersonalizados=[];resultado=null;mostrarEventos();document.getElementById('graficas').innerHTML='<p>Valores restaurados. Pulse Ejecutar simulacion para generar nuevas curvas.</p>';document.getElementById('estado').textContent='Parametros y graficas restaurados.'}
function exportar(){if(!resultado){document.getElementById('estado').textContent='Primero ejecute una simulacion.';return}let filas=resultado.historial,campos=Object.keys(filas[0]),csv=[campos.join(',')];filas.forEach(f=>csv.push(campos.map(k=>f[k]).join(',')));let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv.join('\n')],{type:'text/csv'}));a.download='paciente_virtual.csv';a.click();URL.revokeObjectURL(a.href)}
function descargarTexto(nombre,texto,tipo){let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([texto],{type:tipo}));a.download=nombre;a.click();URL.revokeObjectURL(a.href)}
function exportarExperimento(){let parametros={};['duracion_s','volumen_sanguineo','resistencia','contractilidad','factor_ventilatorio','hemoglobina','bicarbonato'].forEach(k=>parametros[k]=Number(document.getElementById(k).value));let curvas=[...document.querySelectorAll('#variables input:checked')].map(i=>i.value),experimento={formato:'paciente_virtual_experimento',version_formato:1,version_simulador:'1.0.0',escenario:document.getElementById('escenario').value,parametros,eventos:eventosPersonalizados,comparar_basal:document.getElementById('comparar_basal').checked,curvas};descargarTexto('experimento_paciente_virtual.json',JSON.stringify(experimento,null,2),'application/json');document.getElementById('estado').textContent='Experimento guardado.'}
async function cargarExperimento(input){try{let archivo=input.files[0];if(!archivo)return;let e=JSON.parse(await archivo.text());if(e.formato!=='paciente_virtual_experimento'||e.version_formato!==1)throw Error('Formato de experimento no compatible');if(!['basal','hemorragia','aumento_resistencia','hipoventilacion'].includes(e.escenario))throw Error('Escenario no reconocido');document.getElementById('escenario').value=e.escenario;let permitidos=['duracion_s','volumen_sanguineo','resistencia','contractilidad','factor_ventilatorio','hemoglobina','bicarbonato'];permitidos.forEach(k=>{if(Number.isFinite(Number(e.parametros?.[k])))document.getElementById(k).value=e.parametros[k]});eventosPersonalizados=Array.isArray(e.eventos)?e.eventos.filter(x=>x&&typeof x.variable==='string'&&Number.isFinite(Number(x.tiempo_s))&&Number.isFinite(Number(x.valor))&&Number.isFinite(Number(x.duracion_s||0))).map(x=>({variable:x.variable,tiempo_s:Number(x.tiempo_s),valor:Number(x.valor),duracion_s:Number(x.duracion_s||0)})):[];document.getElementById('comparar_basal').checked=Boolean(e.comparar_basal);mostrarEventos();if(Array.isArray(e.curvas)){document.querySelectorAll('#variables input').forEach(i=>i.checked=e.curvas.includes(i.value))}resultado=null;document.getElementById('graficas').innerHTML='<p>Experimento cargado. Pulse Ejecutar simulacion para calcular las curvas.</p>';document.getElementById('analisis').innerHTML='';document.getElementById('sensibilidad').innerHTML='';document.getElementById('estado').textContent='Experimento cargado; todavía no fue ejecutado.'}catch(error){document.getElementById('estado').textContent='Error al cargar: '+error.message}finally{input.value=''}}
function crearSelectores(){let caja=document.getElementById('variables'),pred=['frecuencia_cardiaca','presion_arterial_media','presion_arterial_co2','frecuencia_respiratoria'];Object.entries(resultado.variables).forEach(([k,v])=>{let l=document.createElement('label'),i=document.createElement('input');i.type='checkbox';i.value=k;i.checked=pred.includes(k);i.onchange=dibujarTodo;l.append(i,document.createTextNode(v));caja.append(l)})}
function dibujarTodo(){if(!resultado)return;let ks=[...document.querySelectorAll('#variables input:checked')].map(i=>i.value),zona=document.getElementById('graficas');zona.innerHTML='';ks.forEach(k=>{let tarjeta=document.createElement('div');tarjeta.className='grafica';let titulo=document.createElement('h3'),canvas=document.createElement('canvas'),res=document.createElement('div');canvas.width=700;canvas.height=300;res.className='resumen';titulo.textContent=resultado.variables[k];tarjeta.append(titulo,canvas,res);zona.append(tarjeta);dibujar(canvas,res,k);activarTooltipFisiologico(canvas,k)})}
function dibujar(c,res,k){let datos=resultado.historial,ref=resultado.historial_referencia||[],x=c.getContext('2d'),w=c.width,h=c.height,m=45,ys=datos.map(d=>d[k]),yr=ref.map(d=>d[k]),todos=ys.concat(yr),ts=datos.map(d=>d.tiempo_s),ymin=Math.min(...todos),ymax=Math.max(...todos);x.clearRect(0,0,w,h);if(ymax==ymin){ymin-=1;ymax+=1}let margen=(ymax-ymin)*.08;ymin-=margen;ymax+=margen;x.strokeStyle='#d7dee6';for(let i=0;i<=4;i++){let py=m+(h-2*m)*i/4;x.beginPath();x.moveTo(m,py);x.lineTo(w-m,py);x.stroke();x.fillStyle='#526273';x.fillText((ymax-(ymax-ymin)*i/4).toFixed(1),3,py+4)}resultado.eventos.forEach(e=>{let px=m+(w-2*m)*(e.tiempo_s-ts[0])/(ts.at(-1)-ts[0]);x.save();x.setLineDash([5,4]);x.strokeStyle='#d35400';x.beginPath();x.moveTo(px,m);x.lineTo(px,h-m);x.stroke();x.restore();x.fillStyle='#d35400';x.fillText(e.nombre,px+3,m+10)});trazar(x,datos,k,ts,ymin,ymax,w,h,m,'#1677b8',false);if(ref.length){trazar(x,ref,k,ref.map(d=>d.tiempo_s),ymin,ymax,w,h,m,'#8293a5',true);x.fillStyle='#1677b8';x.fillText('Configurado',w-170,18);x.fillStyle='#8293a5';x.fillText('Basal',w-80,18)}x.fillStyle='#526273';x.fillText('0 s',m,h-10);x.fillText(ts.at(-1).toFixed(0)+' s',w-m-25,h-10);x.fillText('Tiempo (s)',w/2-28,h-10);x.save();x.translate(13,h/2+18);x.rotate(-Math.PI/2);x.fillText('Valor',0,0);x.restore();res.textContent=`Inicial ${ys[0].toFixed(2)} · Min ${Math.min(...ys).toFixed(2)} · Max ${Math.max(...ys).toFixed(2)} · Final ${ys.at(-1).toFixed(2)}`}
function trazar(x,datos,k,ts,ymin,ymax,w,h,m,color,punteada){x.save();x.strokeStyle=color;x.lineWidth=2.5;if(punteada)x.setLineDash([7,5]);x.beginPath();datos.forEach((d,i)=>{let px=m+(w-2*m)*(ts[i]-ts[0])/(ts.at(-1)-ts[0]),py=h-m-(h-2*m)*(d[k]-ymin)/(ymax-ymin);i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();x.restore()}
function obtenerTooltip(c){let contenedor=c.parentElement,t=contenedor.querySelector('.tooltip-grafica');if(!t){t=document.createElement('div');t.className='tooltip-grafica';contenedor.append(t)}return t}
function dibujarCruceta(c,px,py,m){let x=c.getContext('2d');x.save();x.setLineDash([6,5]);x.strokeStyle='#263746';x.lineWidth=1.2;x.beginPath();x.moveTo(px,m);x.lineTo(px,c.height-m);x.moveTo(m,py);x.lineTo(c.width-m,py);x.stroke();x.restore();x.beginPath();x.arc(px,py,4,0,Math.PI*2);x.fillStyle='#263746';x.fill()}
function activarTooltipFisiologico(c,k){c.onmousemove=e=>{let r=c.getBoundingClientRect(),m=45,xCanvas=(e.clientX-r.left)*c.width/r.width,fraccion=Math.max(0,Math.min(1,(xCanvas-m)/(c.width-2*m))),datos=resultado.historial,i=Math.round(fraccion*(datos.length-1)),p=datos[i],ref=resultado.historial_referencia||[],todos=datos.map(d=>d[k]).concat(ref.map(d=>d[k])),ymin=Math.min(...todos),ymax=Math.max(...todos);if(ymax===ymin){ymin-=1;ymax+=1}let margen=(ymax-ymin)*.08;ymin-=margen;ymax+=margen;dibujar(c,c.parentElement.querySelector('.resumen'),k);let px=m+(c.width-2*m)*(p.tiempo_s-datos[0].tiempo_s)/(datos.at(-1).tiempo_s-datos[0].tiempo_s),py=c.height-m-(c.height-2*m)*(p[k]-ymin)/(ymax-ymin);dibujarCruceta(c,px,py,m);let t=obtenerTooltip(c);t.innerHTML=`<b>${resultado.variables[k]}</b><br>Tiempo: ${p.tiempo_s.toFixed(2)} s<br>Valor: ${p[k].toFixed(3)}`;t.style.display='block';t.style.left=(e.clientX+12)+'px';t.style.top=(e.clientY+12)+'px'};c.onmouseleave=()=>{dibujar(c,c.parentElement.querySelector('.resumen'),k);obtenerTooltip(c).style.display='none'}}
</script></body></html>'''


class Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path != "/":
            self.send_error(404); return
        self._responder(200, "text/html; charset=utf-8", HTML.encode())

    def do_POST(self):
        ruta = urlparse(self.path).path
        if ruta not in {"/simular", "/sensibilidad"}:
            self.send_error(404); return
        try:
            largo = int(self.headers.get("Content-Length", "0"))
            datos = json.loads(self.rfile.read(largo))
            resultado = simular(datos) if ruta == "/simular" else analizar_sensibilidad(datos)
            self._responder(200, "application/json", json.dumps(resultado).encode())
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
