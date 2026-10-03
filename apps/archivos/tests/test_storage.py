"""Pruebas de tolerancia del almacenamiento S3/MinIO."""

from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from django.test import SimpleTestCase, override_settings

from apps.archivos.services.storage import (
    abortar_multipart_upload,
    asegurar_bucket,
    eliminar_objeto,
    calcular_sha256_objeto,
    leer_objeto,
    sesion_lectura,
)


def error_s3(codigo, operacion):
    return ClientError(
        {"Error": {"Code": codigo, "Message": codigo}},
        operacion,
    )


@override_settings(
    AWS_STORAGE_BUCKET_NAME="estudios-prueba",
    AWS_S3_ENDPOINT_URL="http://127.0.0.1:9000",
    AWS_S3_REGION_NAME="us-east-1",
)
class AlmacenamientoTests(SimpleTestCase):
    @patch("apps.archivos.services.storage.get_s3_client")
    def test_lectura_cierra_cliente_sin_sesion_externa(self, crear):
        cliente = crear.return_value
        cliente.get_object.return_value["Body"].read.return_value = b"cabecera"
        self.assertEqual(leer_objeto("ficticio", 132), b"cabecera")
        cliente.close.assert_called_once()
        cliente.get_object.return_value["Body"].close.assert_called_once()

    @patch("apps.archivos.services.storage.get_s3_client")
    def test_fallo_de_get_object_cierra_cliente_en_lectura_y_hash(self, crear):
        cliente = crear.return_value
        cliente.get_object.side_effect = RuntimeError("Objeto ausente simulado")
        for operacion in (lambda: leer_objeto("ficticio", 132), lambda: calcular_sha256_objeto("ficticio")):
            with self.assertRaises(RuntimeError):
                operacion()
        self.assertEqual(cliente.close.call_count, 2)
    @patch("apps.archivos.services.storage.get_s3_client")
    def test_analisis_reutiliza_cliente_y_cierra_cada_cuerpo(self, crear):
        cliente = Mock()
        crear.return_value = cliente
        cuerpo = Mock()
        cuerpo.read.return_value = b"cabecera"
        cliente.get_object.return_value = {"Body": cuerpo}
        with sesion_lectura():
            leer_objeto("primero", 132)
            with sesion_lectura():
                leer_objeto("segundo", 256 * 1024)
        crear.assert_called_once()
        self.assertEqual(cuerpo.close.call_count, 2)
        cliente.close.assert_called_once()
        self.assertEqual(cliente.get_object.call_args_list[0].kwargs["Range"], "bytes=0-131")

    @patch("apps.archivos.services.storage.get_s3_client")
    def test_sesion_no_cachea_cliente_entre_analisis(self, crear):
        cliente = Mock()
        crear.return_value = cliente
        cliente.get_object.return_value = {"Body": Mock()}
        for _ in range(2):
            with sesion_lectura():
                leer_objeto("archivo", 132)
        self.assertEqual(crear.call_count, 2)
        self.assertEqual(cliente.close.call_count, 2)

    @patch("apps.archivos.services.storage.get_s3_client")
    @override_settings(DEBUG=True)
    def test_crea_bucket_si_minio_esta_vacio(self, get_s3_client):
        cliente = Mock()
        cliente.head_bucket.side_effect = error_s3("NoSuchBucket", "HeadBucket")
        get_s3_client.return_value = cliente

        resultado = asegurar_bucket()

        self.assertIs(resultado, cliente)
        cliente.create_bucket.assert_called_once_with(Bucket="estudios-prueba")

    @patch("apps.archivos.services.storage.get_s3_client")
    @override_settings(DEBUG=False)
    def test_produccion_no_aprovisiona_bucket(self, get_s3_client):
        from django.core.exceptions import ImproperlyConfigured

        cliente = get_s3_client.return_value
        cliente.head_bucket.side_effect = error_s3("NoSuchBucket", "HeadBucket")
        with self.assertRaises(ImproperlyConfigured):
            asegurar_bucket()
        cliente.create_bucket.assert_not_called()
        cliente.close.assert_called_once()

    @patch("apps.archivos.services.storage.get_s3_client")
    def test_eliminar_es_exitoso_si_el_bucket_ya_no_existe(self, get_s3_client):
        cliente = Mock()
        cliente.delete_object.side_effect = error_s3("NoSuchBucket", "DeleteObject")
        get_s3_client.return_value = cliente

        self.assertTrue(eliminar_objeto("estudios/1/archivo.dcm"))

    @patch("apps.archivos.services.storage.get_s3_client")
    def test_abortar_es_exitoso_si_la_carga_ya_no_existe(self, get_s3_client):
        cliente = Mock()
        cliente.abort_multipart_upload.side_effect = error_s3(
            "NoSuchUpload",
            "AbortMultipartUpload",
        )
        get_s3_client.return_value = cliente

        self.assertTrue(abortar_multipart_upload("estudios/1/archivo.dcm", "upload-1"))
