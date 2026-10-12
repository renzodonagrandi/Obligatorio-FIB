import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paciente_virtual.configuracion import crear_motor_referencia
from paciente_virtual.modelos import AgenteCardiovascular, AgenteNervioso, AgenteRespiratorio
from paciente_virtual.motor import EventoPerturbacion
from paciente_virtual.analisis import analizar_historial


class PruebasPacienteVirtual(unittest.TestCase):
    def test_estado_basal_permanece_estable(self):
        motor = crear_motor_referencia()
        final = motor.ejecutar(10.0)[-1]
        self.assertAlmostEqual(final["frecuencia_cardiaca"], 70.0, places=6)
        self.assertAlmostEqual(final["presion_arterial_media"], 90.2, delta=0.2)
        self.assertAlmostEqual(final["presion_arterial_co2"], 40.0, delta=0.1)

    def test_el_estado_avanza_por_ciclos(self):
        motor = crear_motor_referencia(paso_s=0.2)
        motor.ejecutar_ciclo()
        instantanea = motor.estado.instantanea()
        self.assertEqual(instantanea.ciclo, 1)
        self.assertAlmostEqual(instantanea.tiempo_s, 0.2)

    def test_respiratorio_basal_calcula_ventilacion_alveolar(self):
        motor = crear_motor_referencia()
        agente = AgenteRespiratorio()
        salidas = {p.variable: p.valor for p in agente.calcular(motor.estado.instantanea(), 0.1)}
        self.assertAlmostEqual(salidas["ventilacion_minuto"], 6.0, places=6)
        self.assertAlmostEqual(salidas["ventilacion_alveolar"], 4.32, places=6)
        self.assertGreater(salidas["presion_arterial_o2"], 85.0)
        self.assertGreater(salidas["saturacion_arterial_o2"], 95.0)
        self.assertGreater(salidas["contenido_arterial_o2"], 19.0)
        self.assertAlmostEqual(salidas["ph_arterial"], 7.40, delta=0.02)

    def test_hemoglobina_baja_reduce_aporte_de_oxigeno(self):
        normal = crear_motor_referencia()
        anemia = crear_motor_referencia(valores_iniciales={"hemoglobina": 8.0})
        final_normal = normal.ejecutar(2.0)[-1]
        final_anemia = anemia.ejecutar(2.0)[-1]
        self.assertLess(final_anemia["contenido_arterial_o2"], final_normal["contenido_arterial_o2"])
        self.assertLess(final_anemia["aporte_sistemico_o2"], final_normal["aporte_sistemico_o2"])

    def test_co2_elevado_reduce_ph_estimado(self):
        motor = crear_motor_referencia(valores_iniciales={"presion_arterial_co2": 60.0})
        final = motor.ejecutar(0.1)[-1]
        self.assertLess(final["ph_arterial"], 7.40)

    def test_hipoventilacion_aumenta_objetivo_de_co2(self):
        motor = crear_motor_referencia(valores_iniciales={"impulso_respiratorio": 0.5})
        agente = AgenteRespiratorio()
        estado = motor.estado.instantanea()
        for _ in range(300):
            publicaciones = agente.calcular(estado, 0.1)
            valores = dict(estado.variables)
            for p in publicaciones:
                anterior = valores[p.variable]
                valores[p.variable] = type(anterior)(p.valor, p.unidad, p.calidad, agente.identificador)
            from paciente_virtual.estado import InstantaneaEstado
            estado = InstantaneaEstado(estado.ciclo + 1, estado.tiempo_s + 0.1, valores)
        self.assertGreater(estado.obtener("presion_arterial_co2"), 65.0)
        self.assertLess(estado.obtener("saturacion_arterial_o2"), 95.0)

    def test_hiperventilacion_reduce_co2(self):
        motor = crear_motor_referencia(valores_iniciales={"impulso_respiratorio": 1.5})
        agente = AgenteRespiratorio()
        salida = {p.variable: p.valor for p in agente.calcular(motor.estado.instantanea(), 1.0)}
        self.assertGreater(salida["frecuencia_respiratoria"], 12.0)
        self.assertLess(salida["presion_arterial_co2"], 40.0)

    def test_cardiovascular_basal(self):
        motor = crear_motor_referencia()
        salida = {p.variable: p.valor for p in AgenteCardiovascular().calcular(motor.estado.instantanea(), 0.1)}
        self.assertAlmostEqual(salida["volumen_sistolico"], 70.0, places=6)
        self.assertAlmostEqual(salida["gasto_cardiaco"], 4.9, delta=0.02)
        self.assertAlmostEqual(salida["presion_arterial_media"], 90.2, delta=0.1)

    def test_estimulo_simpatico_aumenta_frecuencia_y_gasto(self):
        motor = crear_motor_referencia(valores_iniciales={"actividad_simpatica": 1.5})
        salida = {p.variable: p.valor for p in AgenteCardiovascular().calcular(motor.estado.instantanea(), 1.0)}
        self.assertGreater(salida["frecuencia_cardiaca"], 70.0)
        self.assertGreater(salida["gasto_cardiaco"], 4.9)

    def test_reduccion_de_volumen_disminuye_volumen_sistolico(self):
        motor = crear_motor_referencia(valores_iniciales={"volumen_sanguineo": 4.0})
        salida = {p.variable: p.valor for p in AgenteCardiovascular().calcular(motor.estado.instantanea(), 0.1)}
        self.assertLess(salida["volumen_sistolico"], 70.0)
        self.assertLess(salida["gasto_cardiaco"], 4.9)

    def test_aumento_resistencia_eleva_presion_y_reduce_volumen_sistolico(self):
        motor = crear_motor_referencia(valores_iniciales={"resistencia_vascular_sistemica": 24.0})
        salida = {p.variable: p.valor for p in AgenteCardiovascular().calcular(motor.estado.instantanea(), 1.0)}
        self.assertLess(salida["volumen_sistolico"], 70.0)
        self.assertGreater(salida["presion_arterial_media"], 90.2)

    def test_nervioso_basal_permanece_en_equilibrio(self):
        motor = crear_motor_referencia()
        salida = {p.variable: p.valor for p in AgenteNervioso().calcular(motor.estado.instantanea(), 0.1)}
        self.assertAlmostEqual(salida["actividad_simpatica"], 1.0, places=6)
        self.assertAlmostEqual(salida["actividad_parasimpatica"], 1.0, places=6)
        self.assertAlmostEqual(salida["impulso_respiratorio"], 1.0, places=6)

    def test_hipotension_activa_simpatico_y_retira_parasimpatico(self):
        motor = crear_motor_referencia(valores_iniciales={"presion_arterial_media": 70.0})
        salida = {p.variable: p.valor for p in AgenteNervioso().calcular(motor.estado.instantanea(), 1.0)}
        self.assertGreater(salida["actividad_simpatica"], 1.0)
        self.assertLess(salida["actividad_parasimpatica"], 1.0)

    def test_hipertension_reduce_simpatico_y_aumenta_parasimpatico(self):
        motor = crear_motor_referencia(valores_iniciales={"presion_arterial_media": 115.0})
        salida = {p.variable: p.valor for p in AgenteNervioso().calcular(motor.estado.instantanea(), 1.0)}
        self.assertLess(salida["actividad_simpatica"], 1.0)
        self.assertGreater(salida["actividad_parasimpatica"], 1.0)

    def test_hipercapnia_e_hipoxemia_aumentan_impulso(self):
        motor = crear_motor_referencia(valores_iniciales={
            "presion_arterial_co2": 50.0,
            "presion_arterial_o2": 55.0,
        })
        salida = {p.variable: p.valor for p in AgenteNervioso().calcular(motor.estado.instantanea(), 1.0)}
        self.assertGreater(salida["impulso_respiratorio"], 1.0)
        self.assertGreater(salida["actividad_simpatica"], 1.0)

    def test_evento_se_aplica_una_sola_vez_en_el_tiempo_programado(self):
        evento = EventoPerturbacion("prueba", 0.2, {"volumen_sanguineo": 4.0})
        motor = crear_motor_referencia(paso_s=0.1, eventos=[evento])
        motor.ejecutar(0.5)
        self.assertEqual(len(motor.eventos_aplicados), 1)
        self.assertAlmostEqual(motor.eventos_aplicados[0]["tiempo_s"], 0.2)
        self.assertAlmostEqual(motor.historial[-1]["volumen_sanguineo"], 4.0)

    def test_hemorragia_reduce_presion_y_activa_barorreflejo(self):
        evento = EventoPerturbacion("hemorragia", 2.0, {"volumen_sanguineo": 4.0})
        motor = crear_motor_referencia(eventos=[evento])
        historial = motor.ejecutar(8.0)
        antes = historial[20]
        minimo_presion = min(f["presion_arterial_media"] for f in historial[21:])
        maximo_simpatico = max(f["actividad_simpatica"] for f in historial[21:])
        self.assertLess(minimo_presion, antes["presion_arterial_media"])
        self.assertGreater(maximo_simpatico, 1.0)

    def test_eventos_sucesivos_conservan_el_ultimo_valor(self):
        eventos = [
            EventoPerturbacion("primero", 0.2, {"contractilidad": 0.8}),
            EventoPerturbacion("segundo", 0.4, {"contractilidad": 1.2}),
        ]
        motor = crear_motor_referencia(eventos=eventos)
        motor.ejecutar(0.6)
        self.assertEqual(len(motor.eventos_aplicados), 2)
        self.assertAlmostEqual(motor.historial[-1]["contractilidad"], 1.2)

    def test_rampa_alcanza_valores_intermedios_y_final(self):
        evento = EventoPerturbacion("perdida_gradual", 1.0, {"volumen_sanguineo": 4.0}, duracion_s=2.0)
        motor = crear_motor_referencia(paso_s=0.1, eventos=[evento])
        historial = motor.ejecutar(3.2)
        en_mitad = min(historial, key=lambda fila: abs(fila["tiempo_s"] - 2.0))
        # El estado confirmado refleja el evento en el cierre del paso siguiente.
        al_final = min(historial, key=lambda fila: abs(fila["tiempo_s"] - 3.1))
        self.assertAlmostEqual(en_mitad["volumen_sanguineo"], 4.5, delta=0.06)
        self.assertAlmostEqual(al_final["volumen_sanguineo"], 4.0, places=6)
        self.assertEqual(len(motor.eventos_aplicados), 1)

    def test_rampa_con_duracion_negativa_es_rechazada(self):
        evento = EventoPerturbacion("invalida", 0.0, {"contractilidad": 0.8}, duracion_s=-1.0)
        motor = crear_motor_referencia(eventos=[evento])
        with self.assertRaises(ValueError):
            motor.ejecutar_ciclo()

    def test_analisis_detecta_caida_de_presion_y_respuesta_simpatica(self):
        evento = EventoPerturbacion("hemorragia", 2.0, {"volumen_sanguineo": 4.0})
        motor = crear_motor_referencia(eventos=[evento])
        historial = motor.ejecutar(12.0)
        analisis = analizar_historial(historial, motor.eventos_aplicados)
        pam = analisis["metricas"]["presion_arterial_media"]
        self.assertLess(pam["minimo"], pam["basal"])
        self.assertTrue(any("simpática" in texto for texto in analisis["resumen"]))

    def test_analisis_basal_informa_estabilidad(self):
        motor = crear_motor_referencia()
        analisis = analizar_historial(motor.ejecutar(5.0), [])
        self.assertIn("basal", analisis["resumen"][0].lower())
        self.assertGreaterEqual(analisis["metricas"]["presion_arterial_media"]["recuperacion_porcentaje"], 99.0)

    def test_resultados_son_consistentes_con_diferentes_pasos(self):
        resultados = []
        for paso in (0.05, 0.1, 0.2, 0.5):
            evento = EventoPerturbacion("hemorragia", 2.0, {"volumen_sanguineo": 4.0})
            motor = crear_motor_referencia(paso_s=paso, eventos=[evento])
            historial = motor.ejecutar(12.0)
            resultados.append(min(f["presion_arterial_media"] for f in historial))
        referencia = resultados[0]
        self.assertTrue(all(abs(valor - referencia) / referencia < 0.02 for valor in resultados[1:]))

    def test_instantanea_no_admite_escritura(self):
        motor = crear_motor_referencia()
        instantanea = motor.estado.instantanea()
        with self.assertRaises(TypeError):
            instantanea.variables["frecuencia_cardiaca"] = None

    def test_co2_elevado_activa_control_y_luego_disminuye(self):
        motor = crear_motor_referencia(valores_iniciales={"presion_arterial_co2": 55.0})
        historial = motor.ejecutar(30.0)
        maximo_impulso = max(fila["impulso_respiratorio"] for fila in historial)
        self.assertGreater(maximo_impulso, 1.1)
        self.assertLess(historial[-1]["presion_arterial_co2"], 55.0)


if __name__ == "__main__":
    unittest.main()
