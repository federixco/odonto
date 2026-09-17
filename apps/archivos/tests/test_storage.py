"""Pruebas de tolerancia del almacenamiento S3/MinIO."""

from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from django.test import SimpleTestCase, override_settings

from apps.archivos.services.storage import (
    abortar_multipart_upload,
    asegurar_bucket,
    eliminar_objeto,
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
    def test_crea_bucket_si_minio_esta_vacio(self, get_s3_client):
        cliente = Mock()
        cliente.head_bucket.side_effect = error_s3("NoSuchBucket", "HeadBucket")
        get_s3_client.return_value = cliente

        resultado = asegurar_bucket()

        self.assertIs(resultado, cliente)
        cliente.create_bucket.assert_called_once_with(Bucket="estudios-prueba")

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
