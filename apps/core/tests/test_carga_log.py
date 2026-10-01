"""El diagnóstico se puede apagar y no registra datos clínicos ni secretos."""

import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.core.carga_log import registrar_carga


class CargaLogTests(SimpleTestCase):
    @override_settings(CARGA_LOG_ENABLED=False)
    @patch("apps.core.carga_log.logger")
    def test_desactivado_no_emite_eventos(self, logger):
        registrar_carga("archivo_completo", archivo_id=1)
        logger.log.assert_not_called()

    @override_settings(CARGA_LOG_ENABLED=True)
    @patch("apps.core.carga_log.logger")
    def test_excepcion_no_expone_mensaje_ni_valores_no_numericos(self, logger):
        secreto = "Paciente DNI 12345678 https://s3.test/?secret=credencial"
        try:
            raise ValueError(secreto)
        except ValueError as error:
            registrar_carga("parser_dicom_error", importacion_id=3,
                            archivo_id=secreto, error=error)
        mensaje = logger.log.call_args.args[1]
        datos = json.loads(mensaje)
        self.assertNotIn(secreto, mensaje)
        self.assertNotIn("archivo_id", datos)
        self.assertEqual(datos["importacion_id"], 3)
        self.assertEqual(datos["error_tipo"], "ValueError")
        self.assertTrue(datos["ubicaciones"])

    @override_settings(CARGA_LOG_ENABLED=True)
    @patch("apps.core.carga_log.logger")
    def test_evento_exitoso_registra_metricas(self, logger):
        registrar_carga("archivo_completo", archivo_id=9, bytes_total=1024, duracion_ms=200)
        datos = json.loads(logger.log.call_args.args[1])
        self.assertEqual(datos["archivo_id"], 9)
        self.assertEqual(datos["bytes_total"], 1024)
        self.assertEqual(datos["duracion_ms"], 200)
