"""Respuestas perdidas y cancelación: almacenamiento completamente simulado."""
from io import BytesIO
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError
from django.test import SimpleTestCase, override_settings
from apps.archivos.services.storage import completar_multipart_upload, calcular_sha256_objeto


class TransferenciasReintentablesTests(SimpleTestCase):
    @patch("apps.archivos.services.storage.get_s3_client")
    def test_complete_perdido_se_recupera_solo_si_head_demuestra_objeto(self, crear):
        crear.return_value.complete_multipart_upload.side_effect = ClientError({"Error":{"Code":"NoSuchUpload"}}, "CompleteMultipartUpload")
        crear.return_value.head_object.return_value = {"ContentLength":10,"ETag":"etag"}
        resultado = completar_multipart_upload("pruebas/archivo", "upload", [{"PartNumber":1,"ETag":"etag"}])
        self.assertEqual(resultado["tamano"], 10)

    @patch("apps.archivos.services.storage.get_s3_client")
    def test_multipart_abortado_sin_objeto_no_se_considera_completo(self, crear):
        crear.return_value.complete_multipart_upload.side_effect = ClientError({"Error":{"Code":"NoSuchUpload"}}, "CompleteMultipartUpload")
        crear.return_value.head_object.side_effect = ClientError({"Error":{"Code":"NoSuchKey"}}, "HeadObject")
        with self.assertRaises(ClientError):
            completar_multipart_upload("pruebas/archivo", "upload", [])

    @override_settings(S3_HASH_CHUNK_SIZE=2)
    @patch("apps.archivos.services.storage.get_s3_client")
    def test_hash_renueva_control_entre_bloques_y_cierra_cuerpo(self, crear):
        cuerpo = BytesIO(b"abcdef")
        crear.return_value.get_object.return_value = {"Body":cuerpo}
        control = Mock()
        resultado = calcular_sha256_objeto("pruebas/archivo", control=control)
        self.assertEqual(len(resultado), 64)
        self.assertEqual(control.call_count, 3)
        self.assertTrue(cuerpo.closed)
        crear.return_value.close.assert_called_once()

    @override_settings(S3_HASH_CHUNK_SIZE=2)
    @patch("apps.archivos.services.storage.get_s3_client")
    def test_interrupcion_del_hash_cierra_stream(self, crear):
        cuerpo = BytesIO(b"abcdef")
        crear.return_value.get_object.return_value = {"Body":cuerpo}
        with self.assertRaises(RuntimeError):
            calcular_sha256_objeto("pruebas/archivo", control=Mock(side_effect=RuntimeError("cancelado")))
        self.assertTrue(cuerpo.closed)
