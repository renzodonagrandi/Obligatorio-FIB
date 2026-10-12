"""Genera las figuras del informe a partir de informe/datos/.

Requiere matplotlib (solo para el informe; el Paciente Virtual no lo necesita):
    python3 -m pip install matplotlib
Uso, desde la raíz del proyecto:
    python3 informe/generar_figuras.py
"""
import csv, json
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.3,'figure.dpi':100,'axes.spines.top':False,'axes.spines.right':False})
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / 'informe' / 'datos'
OUT = str(RAIZ / 'informe' / 'figuras') + '/'
Path(OUT).mkdir(parents=True, exist_ok=True)
ecg=[{k:(float(v) if k!='evento' else v) for k,v in r.items()} for r in csv.DictReader(open(DATOS / 'ecg_simulado.csv', encoding='utf-8'))]
sim=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(open(DATOS / 'simulacion_ecg_60s.csv', encoding='utf-8'))]
an=json.load(open(DATOS / 'analisis_fases_60s.json', encoding='utf-8'))['variables']
T=[r['tiempo_s'] for r in sim]; te=[r['tiempo_s'] for r in ecg]
INI,FIN=5.0,14.0; VIO='#7b3fb0'
def episodio(ax,label=True):
    ax.axvspan(INI,FIN,color=VIO,alpha=.08,lw=0)
    for x in (INI,FIN): ax.axvline(x,color=VIO,ls='--',lw=1)
def col(n): return [r[n] for r in sim]

# Fig 1 ECG
fig=plt.figure(figsize=(11,6.2)); g=fig.add_gridspec(2,2,height_ratios=[1.1,1])
ax=fig.add_subplot(g[0,:]); episodio(ax)
ax.plot(te,[r['ecg_mV'] for r in ecg],color='#b03a2e',lw=.7)
ax.set_xlim(0,20); ax.set_xlabel('Tiempo (s)'); ax.set_ylabel('Amplitud (mV)')
ax.set_title('(a) Señal completa: 5001 muestras a 250 Hz')
ax.text(2.5,1.15,'ritmo basal',ha='center'); ax.text(9.5,1.15,'taquiarritmia',ha='center',color=VIO); ax.text(17,1.15,'ritmo basal',ha='center')
ax.set_ylim(-.4,1.3)
for i,(a,b,tit) in enumerate([(2,4,'(b) Detalle ritmo basal (2–4 s, 70 lpm)'),(8,10,'(c) Detalle taquiarritmia (8–10 s, FC 110–179 lpm)')]):
    z=fig.add_subplot(g[1,i]); s=[r for r in ecg if a<=r['tiempo_s']<=b]
    z.plot([r['tiempo_s'] for r in s],[r['ecg_mV'] for r in s],color='#b03a2e',lw=1)
    z.set_xlim(a,b); z.set_ylim(-.4,1.3); z.set_title(tit); z.set_xlabel('Tiempo (s)'); z.set_ylabel('Amplitud (mV)')
fig.tight_layout(); fig.savefig(OUT+'fig1_ecg.png',dpi=200); plt.close(fig)

# Fig 2 variables
vars_=[('frecuencia_cardiaca','FC (latido/min)','#1677b8'),('volumen_sistolico','VS (mL/latido)','#1677b8'),('gasto_cardiaco','GC (L/min)','#1677b8'),('presion_arterial_media','PAM (mmHg)','#1677b8'),('aporte_sistemico_o2','DO2 (mL/min)','#1677b8')]
fig,axs=plt.subplots(5,1,figsize=(10,12.5),sharex=True)
for ax,(k,et,c) in zip(axs,vars_):
    episodio(ax); a=an[k]
    ax.axhline(a['basal'],color='#8293a5',ls=':',lw=1.2,label=f"basal ≈ {a['basal']:.4g}")
    ax.plot(T[1:],col(k)[1:],color=c,lw=1.8)
    ax.set_ylabel(et)
    d,p=a['durante'],a['despues']
    # extremos relevantes
    if k=='frecuencia_cardiaca':
        pts=[(d['tiempo_maximo_s'],d['maximo'],'máx. %.1f'%d['maximo'])]
    else:
        pts=[(d['tiempo_minimo_s'],d['minimo'],'mín. %.4g'%d['minimo']),(p['tiempo_maximo_s'],p['maximo'],'máx. %.4g'%p['maximo'])]
    for t,v,txt in pts:
        ax.plot(t,v,'o',color='#263746',ms=4); ax.annotate(f'{txt} @ {t:.1f} s',(t,v),xytext=(8,4),textcoords='offset points',fontsize=8.5)
    if a['tiempo_recuperacion_s']:
        ax.axvline(a['tiempo_recuperacion_s'],color='#2e7d32',ls='-.',lw=1)
        ax.text(a['tiempo_recuperacion_s']+.5,ax.get_ylim()[0]+(ax.get_ylim()[1]-ax.get_ylim()[0])*.08,f"±2 % desde {a['tiempo_recuperacion_s']:.1f} s",color='#2e7d32',fontsize=8.5)
    ax.legend(loc='upper right',fontsize=8.5,frameon=False)
axs[0].set_title('Respuesta del Paciente Virtual al episodio (franja violeta: 5–14 s)')
axs[-1].set_xlabel('Tiempo (s)'); axs[-1].set_xlim(0,60)
fig.tight_layout(); fig.savefig(OUT+'fig2_variables_cardiovasculares.png',dpi=200); plt.close(fig)

# Fig 3 entradas
fig,axs=plt.subplots(2,1,figsize=(10,6.5),sharex=True)
ax=axs[0]; episodio(ax)
ax.plot(te,[r['frecuencia_cardiaca_lpm'] for r in ecg],color='#c9a0dc',lw=.8,label='FC en el CSV (250 Hz)')
ax.step(T[1:],col('frecuencia_cardiaca_objetivo')[1:],where='post',color=VIO,lw=1.3,label='frecuencia_cardiaca_objetivo publicada (10 Hz)')
ax.plot(T[1:],col('frecuencia_cardiaca')[1:],color='#1677b8',lw=2,label='frecuencia_cardiaca del paciente (τ = 3 s)')
ax.set_ylabel('latido/min'); ax.legend(fontsize=8.5,loc='upper right',frameon=False); ax.set_ylim(50,200)
ax.set_title('(a) Frecuencia: entrada externa y respuesta del modelo')
ax=axs[1]; episodio(ax)
ax.plot(te,[r['eficiencia_ritmo'] for r in ecg],color='#c9a0dc',lw=2.5,label='eficiencia en el CSV')
ax.step(T[1:],col('eficiencia_ritmo')[1:],where='post',color=VIO,lw=1.3,label='eficiencia_ritmo publicada')
ax.set_ylabel('adimensional'); ax.set_ylim(.3,1.1); ax.legend(fontsize=8.5,loc='center left',bbox_to_anchor=(0.52,0.45),frameon=False)
ax.axvline(20,color='#c77c00',ls=':',lw=1.2); ax.text(20.3,.80,'fin de la señal: se retiene la última\nmuestra (calidad DEGRADADO)',fontsize=8.5,color='#c77c00')
ax.set_title('(b) Eficiencia del ritmo'); ax.set_xlabel('Tiempo (s)'); ax.set_xlim(0,30)
fig.tight_layout(); fig.savefig(OUT+'fig3_entradas_agente.png',dpi=200); plt.close(fig)

# Fig 4 sincronizacion zoom
fig,axs=plt.subplots(3,1,figsize=(10,8.2),sharex=True); a,b=4.75,5.65
se=[r for r in ecg if a<=r['tiempo_s']<=b]; ss=[r for r in sim if a-0.1<=r['tiempo_s']<=b]
for ax in axs:
    for k in range(48,57): ax.axvline(k/10,color='#8293a5',lw=.6,alpha=.6)
    ax.axvline(5.0,color=VIO,ls='--',lw=1)
ax=axs[0]
ax.plot([r['tiempo_s'] for r in se],[r['eficiencia_ritmo'] for r in se],'.',color='#c9a0dc',ms=4,label='muestras del CSV (cada 4 ms)')
ax.step([r['tiempo_s'] for r in ss],[r['eficiencia_ritmo'] for r in ss],where='post',color=VIO,lw=1.6,label='valor confirmado en el estado global')
ax.annotate('t = 5,1: promedio de (4,9; 5,0]\n24 basales + 1 arritmia → 0,978',(5.1,.978),xytext=(5.25,.80),fontsize=8.5,arrowprops=dict(arrowstyle='->',color='#263746'))
ax.set_ylabel('eficiencia'); ax.legend(fontsize=8.5,loc='upper right',frameon=False); ax.set_ylim(.35,1.08)
ax.set_title('(a) Selección del agente: promedio causal de la ventana (t − Δt, t]')
ax=axs[1]
ax.plot([r['tiempo_s'] for r in se],[r['frecuencia_cardiaca_lpm'] for r in se],'.',color='#c9a0dc',ms=4,label='FC del CSV')
ax.step([r['tiempo_s'] for r in ss],[r['frecuencia_cardiaca_objetivo'] for r in ss],where='post',color=VIO,lw=1.6,label='FC objetivo confirmada')
ax.set_ylabel('latido/min'); ax.legend(fontsize=8.5,loc='lower right',frameon=False)
ax.set_title('(b) Frecuencia cardíaca objetivo')
ax=axs[2]
ax.plot([r['tiempo_s'] for r in ss],[r['volumen_sistolico'] for r in ss],'o-',color='#1677b8',ms=4,label='VS (mL/latido)')
ax2=ax.twinx(); ax2.plot([r['tiempo_s'] for r in ss],[r['gasto_cardiaco'] for r in ss],'s--',color='#d35400',ms=3.5,label='GC (L/min)')
ax2.set_ylabel('GC (L/min)',color='#d35400'); ax2.spines['right'].set_visible(True); ax2.grid(False)
ax.annotate('t = 5,3: VS = 70 × 0,45 = 31,5',(5.3,31.5),xytext=(5.38,50),fontsize=8.5,arrowprops=dict(arrowstyle='->',color='#263746'))
ax.set_ylabel('VS (mL/latido)',color='#1677b8'); ax.set_xlabel('Tiempo (s) — líneas grises: ciclos del motor (Δt = 0,1 s)')
ax.set_title('(c) Respuesta cardiovascular: un ciclo de retardo entre publicación y efecto')
ax.set_xlim(a,b)
fig.tight_layout(); fig.savefig(OUT+'fig4_sincronizacion.png',dpi=200); plt.close(fig)

# Fig 5 nervioso
fig,ax=plt.subplots(figsize=(10,3.6)); episodio(ax)
ax.plot(T,col('actividad_simpatica'),color='#c62828',lw=1.8,label='actividad simpática')
ax.plot(T,col('actividad_parasimpatica'),color='#2e7d32',lw=1.8,label='actividad parasimpática')
ax.axhline(1,color='#8293a5',ls=':',lw=1.2)
ax.set_xlim(0,60); ax.set_xlabel('Tiempo (s)'); ax.set_ylabel('adimensional'); ax.legend(frameon=False,fontsize=9)
ax.set_title('Respuesta del barorreflejo (agente nervioso)')
fig.tight_layout(); fig.savefig(OUT+'fig5_barorreflejo.png',dpi=200); plt.close(fig)
print('Figuras generadas en', OUT)
