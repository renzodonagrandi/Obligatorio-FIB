import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import agente_externo_ecg
import interfaz_web
from paciente_virtual.fuente_ecg import ErrorSenalECG


class PruebasInterfazECG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "ecg.csv"
            agente_externo_ecg.generar_archivo(
                ruta=ruta, duracion_s=20.0, frecuencia_cardiaca_lpm=70.0,
                inicio_arritmia_s=5.0, fin_arritmia_s=14.0,
            )
            cls.contenido = ruta.read_text(encoding="utf-8")

    def _ecg(self, contenido=None):
        return {"nombre": "ecg.csv", "contenido": self.contenido if contenido is None else contenido}

    def test_cargar_ecg_devuelve_resumen_y_muestras(self):
        respuesta = interfaz_web.cargar_ecg(self._ecg())
        self.assertEqual(len(respuesta["muestras"]["tiempo_s"]), 5001)
        self.assertEqual(len(respuesta["muestras"]["ecg_mV"]), 5001)
        self.assertEqual(len(respuesta["muestras"]["evento"]), 5001)
        self.assertEqual(respuesta["resumen"]["calidad"], "valido")
        self.assertEqual(respuesta["resumen"]["origen"], "ecg.csv")
        self.assertEqual(len(respuesta["resumen"]["episodios"]), 3)
        json.dumps(respuesta)

    def test_cargar_ecg_rechaza_archivo_invalido(self):
        sin_columna = "tiempo_s,ecg_mV,frecuencia_cardiaca_lpm,evento\n0,0.1,70,ritmo_basal\n"
        with self.assertRaises(ErrorSenalECG) as contexto:
            interfaz_web.cargar_ecg(self._ecg(sin_columna))
        self.assertIn("eficiencia_ritmo", str(contexto.exception))
        with self.assertRaises(ErrorSenalECG) as contexto:
            interfaz_web.cargar_ecg(self._ecg(""))
        self.assertIn("el archivo está vacío", str(contexto.exception))
        self.assertNotIn("No se seleccionó", str(contexto.exception))

    def test_cargar_ecg_sin_archivo_seleccionado(self):
        for datos in (None, {}, {"nombre": "ecg.csv"}, {"contenido": "x"}):
            with self.subTest(datos=datos), self.assertRaises(ErrorSenalECG) as contexto:
                interfaz_web.cargar_ecg(datos)
            self.assertIn("No se seleccionó ningún archivo", str(contexto.exception))

    def test_simular_con_ecg_modifica_al_paciente(self):
        respuesta = interfaz_web.simular({"escenario": "basal", "duracion_s": "60", "ecg": self._ecg()})
        historial = respuesta["historial"]
        fila_10 = min(historial, key=lambda f: abs(f["tiempo_s"] - 10.0))
        self.assertGreater(fila_10["frecuencia_cardiaca_objetivo"], 100)
        self.assertLess(min(f["volumen_sistolico"] for f in historial), 40)
        marcadores = {m["nombre"]: m["tiempo_s"] for m in respuesta["marcadores_ecg"]}
        self.assertAlmostEqual(marcadores["inicio taquiarritmia"], 5.0)
        self.assertAlmostEqual(marcadores["fin taquiarritmia"], 14.0)
        self.assertIsNotNone(respuesta["analisis_ecg"])
        self.assertEqual(respuesta["ecg"]["calidad"], "valido")
        self.assertEqual(respuesta["advertencias_simulacion"], [])
        resumen = " ".join(respuesta["analisis"]["resumen"])
        self.assertNotIn("basal sin perturbaciones", resumen)
        self.assertTrue(respuesta["analisis"]["resumen"][0].startswith("Señal ECG externa 'ecg.csv'"))
        json.dumps(respuesta)

    def test_simular_sin_ecg_no_cambia(self):
        respuesta = interfaz_web.simular({"escenario": "basal", "duracion_s": "60"})
        self.assertTrue(all(f["frecuencia_cardiaca_objetivo"] == 0.0 for f in respuesta["historial"]))
        self.assertEqual(respuesta["marcadores_ecg"], [])
        self.assertEqual(respuesta["advertencias_simulacion"], [])
        self.assertNotIn("ecg", respuesta)
        self.assertNotIn("analisis_ecg", respuesta)

    def test_simular_con_ecg_invalido_no_simula(self):
        with self.assertRaises(ErrorSenalECG):
            interfaz_web.simular({"escenario": "basal", "duracion_s": "60",
                                  "ecg": self._ecg("tiempo_s,ecg_mV\n0,abc\n")})

    def test_simular_con_ecg_y_duracion_corta_advierte(self):
        respuesta = interfaz_web.simular({"escenario": "basal", "duracion_s": "10", "ecg": self._ecg()})
        self.assertIsNone(respuesta["analisis_ecg"])
        advertencias = respuesta["advertencias_simulacion"]
        self.assertTrue(any("no cubre el fin del episodio (14 s)" in a for a in advertencias))
        self.assertTrue(any("se recomiendan al menos 34 s" in a for a in advertencias))

    def test_sensibilidad_y_comparacion_basal_con_ecg(self):
        filas = interfaz_web.analizar_sensibilidad(
            {"escenario": "basal", "duracion_s": "30", "ecg": self._ecg()})["filas"]
        self.assertEqual(len(filas), 4)
        self.assertTrue(all(f["fc_maxima"] > 100 for f in filas))
        respuesta = interfaz_web.simular({"escenario": "basal", "duracion_s": "30", "paso_s": "0.2",
                                          "comparar_basal": True, "ecg": self._ecg()})
        referencia = respuesta["historial_referencia"]
        self.assertAlmostEqual(referencia[1]["tiempo_s"], 0.2)
        self.assertTrue(all(f["frecuencia_cardiaca_objetivo"] == 0.0 for f in referencia))


if __name__ == "__main__":
    unittest.main()
