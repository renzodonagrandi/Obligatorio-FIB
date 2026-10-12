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
from paciente_virtual.fuente_ecg import (
    CalidadSenal,
    ErrorSenalECG,
    MuestraECG,
    interpretar_csv_ecg,
    leer_csv_ecg,
    validar_muestras,
)

ENCABEZADO = "tiempo_s,ecg_mV,frecuencia_cardiaca_lpm,eficiencia_ritmo,evento\n"


class PruebasAgenteECG(unittest.TestCase):
    def setUp(self):
        directorio = tempfile.TemporaryDirectory()
        self.addCleanup(directorio.cleanup)
        self.directorio = Path(directorio.name)

    def _csv(self, texto):
        ruta = self.directorio / "senal.csv"
        ruta.write_text(texto, encoding="utf-8")
        return ruta

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


if __name__ == "__main__":
    unittest.main()
