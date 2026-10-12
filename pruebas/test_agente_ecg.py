import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import agente_externo_ecg
from paciente_virtual.analisis import analizar_por_fases
from paciente_virtual.configuracion import CATALOGO, crear_motor_referencia
from paciente_virtual.ecg import AgenteECG, FuenteMuestrasECG, SeleccionECG
from paciente_virtual.estado import CalidadDato, InstantaneaEstado
from paciente_virtual.fuente_ecg import (
    CalidadSenal,
    ErrorSenalECG,
    MuestraECG,
    interpretar_csv_ecg,
    leer_csv_ecg,
    validar_muestras,
)

ENCABEZADO = "tiempo_s,ecg_mV,frecuencia_cardiaca_lpm,eficiencia_ritmo,evento\n"
VARIABLES_CARDIACAS = ("frecuencia_cardiaca", "volumen_sistolico", "gasto_cardiaco",
                       "presion_arterial_media", "aporte_sistemico_o2")


def _instantanea(tiempo_s):
    return InstantaneaEstado(ciclo=0, tiempo_s=tiempo_s, variables=MappingProxyType({}))


def _fila(historial, tiempo_s):
    return next(f for f in historial if abs(f["tiempo_s"] - tiempo_s) < 1e-6)


class PruebasAgenteECG(unittest.TestCase):
    def setUp(self):
        directorio = tempfile.TemporaryDirectory()
        self.addCleanup(directorio.cleanup)
        self.directorio = Path(directorio.name)

    def _csv(self, texto):
        ruta = self.directorio / "senal.csv"
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def _senal_real(self, duracion_s=20.0, inicio_s=5.0, fin_s=14.0):
        ruta = self.directorio / f"ecg_{duracion_s:g}_{inicio_s:g}_{fin_s:g}.csv"
        agente_externo_ecg.generar_archivo(
            ruta=ruta, duracion_s=duracion_s, frecuencia_cardiaca_lpm=70.0,
            inicio_arritmia_s=inicio_s, fin_arritmia_s=fin_s,
        )
        return leer_csv_ecg(ruta)

    def _senal_escalon(self, desde_s=0.0):
        """t = 0, 0.025, ..., 2.0; FC 60/eficiencia 1.0 antes de t=1.0 y 120/0.5 desde t=1.0."""
        muestras = []
        for indice in range(round(desde_s / 0.025), 81):
            arritmia = indice >= 40
            muestras.append(MuestraECG(
                round(indice * 0.025, 6), 0.0,
                120.0 if arritmia else 60.0, 0.5 if arritmia else 1.0,
                "taquiarritmia" if arritmia else "ritmo_basal",
            ))
        return validar_muestras(muestras, "escalon")

    def test_lee_y_valida_un_csv_correcto(self):
        ruta = self.directorio / "ecg.csv"
        agente_externo_ecg.generar_archivo(
            ruta=ruta, duracion_s=20.0, frecuencia_cardiaca_lpm=70.0,
            inicio_arritmia_s=5.0, fin_arritmia_s=14.0,
        )
        senal = leer_csv_ecg(ruta)

        self.assertEqual(senal.cantidad_muestras, 5001)
        for muestra in (senal.muestras[0], senal.muestras[2000]):
            self.assertIsInstance(muestra.tiempo_s, float)
            self.assertIsInstance(muestra.ecg_mV, float)
            self.assertIsInstance(muestra.frecuencia_cardiaca_lpm, float)
            self.assertIsInstance(muestra.eficiencia_ritmo, float)
        self.assertAlmostEqual(senal.duracion_s, 20.0)
        self.assertAlmostEqual(senal.frecuencia_muestreo_hz, 250.0, places=6)
        self.assertEqual(senal.calidad, CalidadSenal.VALIDO)
        self.assertEqual(senal.advertencias, ())
        self.assertAlmostEqual(senal.amplitud_minima_mV, -0.255279, places=5)
        self.assertAlmostEqual(senal.amplitud_maxima_mV, 1.084231, places=5)

        esperados = [("ritmo_basal", 0.0, 5.0), ("taquiarritmia", 5.0, 14.0),
                     ("ritmo_basal", 14.0, 20.0)]
        episodios = senal.episodios()
        self.assertEqual(len(episodios), len(esperados))
        for episodio, (evento, inicio, fin) in zip(episodios, esperados):
            self.assertEqual(episodio.evento, evento)
            self.assertAlmostEqual(episodio.inicio_s, inicio)
            self.assertAlmostEqual(episodio.fin_s, fin)

        resumen = json.loads(json.dumps(senal.resumen()))
        self.assertEqual(resumen["calidad"], "valido")
        self.assertEqual(resumen["origen"], "ecg.csv")

    def test_rechaza_un_csv_incorrecto(self):
        self.assertTrue(issubclass(ErrorSenalECG, ValueError))
        fila = "0.004,0.1,70,1.0,ritmo_basal\n"
        casos = {
            "falta una columna": (
                "tiempo_s,ecg_mV,frecuencia_cardiaca_lpm,evento\n0,0.1,70,ritmo_basal\n",
                "eficiencia_ritmo"),
            "valor vacío": (ENCABEZADO + "0,,70,1.0,ritmo_basal\n" + fila, "valor vacío en 'ecg_mV'"),
            "no numérico": (ENCABEZADO + "0,abc,70,1.0,ritmo_basal\n" + fila, "'abc'"),
            "nan": (ENCABEZADO + "0,nan,70,1.0,ritmo_basal\n" + fila, "'nan'"),
            "FC 250": (ENCABEZADO + "0,0.1,250,1.0,ritmo_basal\n" + fila, "frecuencia_cardiaca_lpm"),
            "FC 10": (ENCABEZADO + "0,0.1,10,1.0,ritmo_basal\n" + fila, "frecuencia_cardiaca_lpm"),
            "eficiencia 0.1": (ENCABEZADO + "0,0.1,70,0.1,ritmo_basal\n" + fila, "eficiencia_ritmo"),
            "eficiencia 1.5": (ENCABEZADO + "0,0.1,70,1.5,ritmo_basal\n" + fila, "eficiencia_ritmo"),
            "una sola muestra": (ENCABEZADO + fila, "al menos 2 muestras"),
            "solo encabezado": (ENCABEZADO, "al menos 2 muestras"),
            "texto vacío": ("", "vacío"),
            "evento vacío": (ENCABEZADO + "0,0.1,70,1.0,\n" + fila, "valor vacío en 'evento'"),
        }
        for nombre, (texto, esperado) in casos.items():
            with self.subTest(nombre):
                with self.assertRaises(ErrorSenalECG) as contexto:
                    leer_csv_ecg(self._csv(texto))
                self.assertIn(esperado, str(contexto.exception))

        with self.subTest("archivo inexistente"):
            ruta = self.directorio / "no_existe.csv"
            with self.assertRaises(ErrorSenalECG) as contexto:
                leer_csv_ecg(ruta)
            self.assertIn("no_existe.csv", str(contexto.exception))

        with self.subTest("ruta None"):
            with self.assertRaises(ErrorSenalECG) as contexto:
                leer_csv_ecg(None)
            self.assertIn("No se seleccionó ningún archivo", str(contexto.exception))

        with self.subTest("varios errores"):
            texto = (ENCABEZADO + "0,abc,70,1.0,ritmo_basal\n"
                     "0.004,0.1,250,1.0,ritmo_basal\n0.008,0.1,70,1.5,ritmo_basal\n")
            with self.assertRaises(ErrorSenalECG) as contexto:
                leer_csv_ecg(self._csv(texto))
            error = contexto.exception
            self.assertEqual(len(error.errores), 3)
            self.assertIn("línea 2", str(error))
            self.assertIn("frecuencia_cardiaca_lpm", str(error))
            self.assertIn("eficiencia_ritmo", str(error))

    def test_rechaza_tiempos_repetidos_o_desordenados(self):
        casos = {
            "tiempo repetido": ("0.0", "0.004", "0.004", "tiempo repetido"),
            "tiempo desordenado": ("0.0", "0.008", "0.004", "tiempos desordenados"),
            "tiempo negativo": ("-0.004", "0.0", "0.004", "tiempo negativo"),
        }
        for nombre, (*tiempos, esperado) in casos.items():
            with self.subTest(nombre):
                texto = ENCABEZADO + "".join(f"{t},0.1,70,1.0,ritmo_basal\n" for t in tiempos)
                with self.assertRaises(ErrorSenalECG) as contexto:
                    interpretar_csv_ecg(texto, "prueba")
                self.assertIn(esperado, str(contexto.exception))

        texto = ENCABEZADO + "".join(
            f"{t},0.1,70,1.0,ritmo_basal\n" for t in ("0.0", "0.004", "0.008"))
        senal = interpretar_csv_ecg(texto, "prueba")
        self.assertEqual(senal.tiempos_s, (0.0, 0.004, 0.008))
        self.assertEqual(senal.calidad, CalidadSenal.VALIDO)

    def test_senal_con_advertencias_es_degradada(self):
        muestras = [MuestraECG(0.004 * i, 0.1, 70.0, 1.0, "ritmo_basal") for i in range(4)]
        muestras.append(MuestraECG(0.016, 0.1, 70.0, 1.0, "fibrilacion"))
        senal = validar_muestras(muestras, "desconocido")
        self.assertEqual(senal.calidad, CalidadSenal.DEGRADADO)
        self.assertTrue(any("fibrilacion" in a for a in senal.advertencias))

        tiempos = [0.0, 0.004, 0.008, 0.028, 0.032, 0.036]
        muestras = [MuestraECG(t, 0.1, 70.0, 1.0, "ritmo_basal") for t in tiempos]
        senal = validar_muestras(muestras, "hueco")
        self.assertEqual(senal.calidad, CalidadSenal.DEGRADADO)
        self.assertTrue(any("pérdida de muestras" in a and "0.008" in a
                            for a in senal.advertencias))

    def test_publica_la_muestra_correspondiente_al_tiempo(self):
        senal = self._senal_escalon()
        agente = AgenteECG(senal)
        self.assertEqual(agente.identificador, "agente_ecg")
        self.assertEqual(agente.entradas, frozenset())
        self.assertEqual(agente.salidas,
                         frozenset({"frecuencia_cardiaca_objetivo", "eficiencia_ritmo"}))

        publicaciones = agente.calcular(_instantanea(0.5), 0.1)
        self.assertEqual(len(publicaciones), 2)
        self.assertEqual({p.variable for p in publicaciones}, agente.salidas)
        por_variable = {p.variable: p for p in publicaciones}
        for variable, unidad in (("frecuencia_cardiaca_objetivo", "latido/min"),
                                 ("eficiencia_ritmo", "1")):
            self.assertEqual(por_variable[variable].unidad, CATALOGO[variable].unidad)
            self.assertEqual(por_variable[variable].unidad, unidad)
            self.assertEqual(por_variable[variable].calidad, CalidadDato.VALIDO)
        self.assertAlmostEqual(por_variable["frecuencia_cardiaca_objetivo"].valor, 60.0)
        self.assertAlmostEqual(por_variable["eficiencia_ritmo"].valor, 1.0)

        seleccion = agente.seleccionar(1.0, 0.1)
        self.assertEqual(seleccion.criterio, "promedio_intervalo")
        self.assertEqual(seleccion.cantidad_muestras, 4)
        self.assertAlmostEqual(seleccion.frecuencia_cardiaca_lpm, 75.0)
        self.assertAlmostEqual(seleccion.eficiencia_ritmo, 0.875)

        for tiempo, paso, cantidad in ((1.1, 0.1, 4), (1.5, 0.5, 20)):
            with self.subTest(tiempo=tiempo, paso=paso):
                seleccion = agente.seleccionar(tiempo, paso)
                self.assertEqual(seleccion.cantidad_muestras, cantidad)
                self.assertAlmostEqual(seleccion.frecuencia_cardiaca_lpm, 120.0)
                self.assertAlmostEqual(seleccion.eficiencia_ritmo, 0.5)

        seleccion = agente.seleccionar(1.01, 0.01)
        self.assertEqual(seleccion.criterio, "retencion_ultima")
        self.assertEqual((seleccion.frecuencia_cardiaca_lpm, seleccion.eficiencia_ritmo), (120.0, 0.5))
        self.assertEqual(seleccion.calidad, CalidadDato.VALIDO)
        self.assertEqual(seleccion.cantidad_muestras, 0)

        seleccion = agente.seleccionar(2.5, 0.1)
        self.assertEqual(seleccion.criterio, "retencion_fin_senal")
        self.assertEqual((seleccion.frecuencia_cardiaca_lpm, seleccion.eficiencia_ritmo), (120.0, 0.5))
        self.assertEqual(seleccion.calidad, CalidadDato.DEGRADADO)

        seleccion = AgenteECG(self._senal_escalon(desde_s=1.0)).seleccionar(0.5, 0.1)
        self.assertEqual(seleccion.criterio, "sin_datos")
        self.assertEqual((seleccion.frecuencia_cardiaca_lpm, seleccion.eficiencia_ritmo), (0.0, 1.0))

        for paso, ultimo_k in ((0.1, 20), (0.05, 40), (0.2, 10)):
            with self.subTest(sin_perdida_ni_duplicacion=paso):
                total = sum(
                    agente.seleccionar(round(k * paso, 12), paso).cantidad_muestras
                    for k in range(ultimo_k + 1)
                )
                self.assertEqual(total, senal.cantidad_muestras)
                self.assertEqual(total, 81)

        self.assertEqual(agente.seleccionar(1.0, 0.1), agente.seleccionar(1.0, 0.1))
        self.assertIsInstance(agente.seleccionar(1.0, 0.1), SeleccionECG)

        senal_real = self._senal_real()
        seleccion = AgenteECG(senal_real).seleccionar(5.1, 0.1)
        frecuencias = [m.frecuencia_cardiaca_lpm for m in senal_real.muestras
                       if 5.0 < m.tiempo_s <= 5.1]
        self.assertAlmostEqual(seleccion.eficiencia_ritmo, 0.45)
        self.assertAlmostEqual(seleccion.frecuencia_cardiaca_lpm, sum(frecuencias) / len(frecuencias))

        motor = crear_motor_referencia(agentes_adicionales=[AgenteECG(senal_real)])
        motor.ejecutar_ciclo()
        self.assertEqual(motor.historial[1]["frecuencia_cardiaca_objetivo"], 70.0)
        motor = crear_motor_referencia()
        motor.ejecutar_ciclo()
        self.assertEqual(motor.historial[1]["frecuencia_cardiaca_objetivo"], 0.0)

    def test_la_arritmia_modifica_el_paciente_y_luego_se_recupera(self):
        senal = self._senal_real()
        historial = crear_motor_referencia(
            paso_s=0.1, agentes_adicionales=[AgenteECG(senal)]).ejecutar(60.0)
        referencia = crear_motor_referencia(paso_s=0.1).ejecutar(60.0)

        antes, antes_ref = _fila(historial, 4.9), _fila(referencia, 4.9)
        for variable in VARIABLES_CARDIACAS:
            with self.subTest(antes=variable):
                self.assertAlmostEqual(antes[variable], antes_ref[variable],
                                       delta=0.005 * abs(antes_ref[variable]))

        self.assertAlmostEqual(_fila(historial, 5.0)["volumen_sistolico"],
                               _fila(referencia, 5.0)["volumen_sistolico"])

        basal = _fila(referencia, 5.0)
        durante = [f for f in historial if 5.0 - 1e-9 <= f["tiempo_s"] <= 14.0 + 1e-9]

        def minimo(variable):
            return min(f[variable] for f in durante)

        def maximo(variable):
            return max(f[variable] for f in durante)

        self.assertLess(minimo("volumen_sistolico"), 0.6 * basal["volumen_sistolico"])
        self.assertGreater(maximo("frecuencia_cardiaca"), basal["frecuencia_cardiaca"] + 40)
        self.assertLess(minimo("presion_arterial_media"), basal["presion_arterial_media"] - 10)
        self.assertLess(minimo("gasto_cardiaco"), 0.8 * basal["gasto_cardiaco"])
        self.assertLess(minimo("aporte_sistemico_o2"), 0.8 * basal["aporte_sistemico_o2"])
        self.assertGreater(maximo("actividad_simpatica"), 1.1)

        self.assertGreater(_fila(historial, 10.0)["frecuencia_cardiaca_objetivo"], 100)
        self.assertEqual(_fila(historial, 15.0)["frecuencia_cardiaca_objetivo"], 70.0)
        self.assertAlmostEqual(_fila(historial, 10.0)["eficiencia_ritmo"], 0.45)
        self.assertAlmostEqual(_fila(historial, 15.0)["eficiencia_ritmo"], 1.0)

        vs_basal = basal["volumen_sistolico"]
        self.assertLess(abs(_fila(historial, 15.0)["volumen_sistolico"] - vs_basal),
                        abs(minimo("volumen_sistolico") - vs_basal))
        final = _fila(historial, 60.0)
        for variable in VARIABLES_CARDIACAS:
            with self.subTest(final=variable):
                self.assertAlmostEqual(final[variable], basal[variable],
                                       delta=0.05 * abs(basal[variable]))

    def test_el_agente_acepta_otra_fuente(self):
        class FuenteConstante:
            calidad = CalidadSenal.VALIDO
            tiempo_final_s = 1000.0
            _muestra = MuestraECG(0.0, 0.0, 90.0, 0.8, "ritmo_basal")

            def muestras_en_intervalo(self, inicio_s, fin_s):
                return (self._muestra,)

            def ultima_muestra_hasta(self, tiempo_s):
                return self._muestra

        fuente = FuenteConstante()
        self.assertIsInstance(fuente, FuenteMuestrasECG)
        publicaciones = {p.variable: p.valor
                         for p in AgenteECG(fuente).calcular(_instantanea(3.0), 0.1)}
        self.assertAlmostEqual(publicaciones["frecuencia_cardiaca_objetivo"], 90.0)
        self.assertAlmostEqual(publicaciones["eficiencia_ritmo"], 0.8)
        with self.assertRaises(TypeError):
            AgenteECG(object())
        self.assertIsInstance(self._senal_escalon(), FuenteMuestrasECG)

    def test_episodio_configurable_no_esta_fijo(self):
        senal = self._senal_real(duracion_s=30.0, inicio_s=8.0, fin_s=20.0)
        arritmias = [e for e in senal.episodios() if e.evento == "taquiarritmia"]
        self.assertEqual(len(arritmias), 1)
        self.assertAlmostEqual(arritmias[0].inicio_s, 8.0)
        self.assertAlmostEqual(arritmias[0].fin_s, 20.0)
        agente = AgenteECG(senal)
        for tiempo, eficiencia in ((10.0, 0.45), (21.0, 1.0)):
            with self.subTest(tiempo=tiempo):
                publicaciones = {p.variable: p.valor
                                 for p in agente.calcular(_instantanea(tiempo), 0.1)}
                self.assertAlmostEqual(publicaciones["eficiencia_ritmo"], eficiencia)

    def test_analisis_por_fases_detecta_cambio_y_recuperacion(self):
        historial = [
            {"tiempo_s": round(i * 0.1, 12), "volumen_sistolico": 5.0 if 10 < i <= 20 else 10.0}
            for i in range(41)
        ]
        analisis = analizar_por_fases(historial, 1.0, 2.0)
        self.assertEqual(list(analisis), ["volumen_sistolico"])
        datos = analisis["volumen_sistolico"]
        self.assertEqual(datos["basal"], 10.0)
        self.assertAlmostEqual(datos["tiempo_inicio_cambio_s"], 1.1)
        self.assertEqual(datos["durante"]["minimo"], 5.0)
        self.assertAlmostEqual(datos["durante"]["tiempo_minimo_s"], 1.1)
        self.assertEqual(datos["valor_fin_episodio"], 5.0)
        self.assertAlmostEqual(datos["tiempo_recuperacion_s"], 2.1)
        self.assertEqual(datos["final"], 10.0)
        self.assertEqual(datos["desviacion_final_porcentaje"], 0.0)
        with self.assertRaises(ValueError):
            analizar_por_fases(historial, 1.0, 5.0)


if __name__ == "__main__":
    unittest.main()
