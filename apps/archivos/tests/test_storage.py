"""Pruebas de tolerancia del almacenamiento S3/MinIO."""

from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from django.test import SimpleTestCase, override_settings

from apps.archivos.services.storage import (
    get_s3_client,
    generar_urls_prefirmadas,
    generar_url_descarga,
    generar_url_previsualizacion,
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
    @patch("boto3.client")
    def test_cliente_verifica_certificados_y_no_expone_secreto_en_endpoint(self, crear):
        get_s3_client()
        self.assertIs(crear.call_args.kwargs["verify"], True)
        self.assertEqual(crear.call_args.kwargs["config"].signature_version, "s3v4")

    @patch("boto3.client")
    def test_cliente_anonimo_no_firma_ni_recibe_nuestras_claves(self, crear):
        from botocore import UNSIGNED

        get_s3_client(anonimo=True)
        self.assertEqual(crear.call_args.kwargs["config"].signature_version, UNSIGNED)
        self.assertIsNone(crear.call_args.kwargs["aws_access_key_id"])
        self.assertIsNone(crear.call_args.kwargs["aws_secret_access_key"])
        self.assertIs(crear.call_args.kwargs["verify"], True)

    @patch("apps.archivos.services.storage.get_s3_client")
    @override_settings(AWS_S3_UPLOAD_EXPIRATION=3600, AWS_S3_DOWNLOAD_EXPIRATION=300,
                       AWS_S3_PREVIEW_EXPIRATION=900, AWS_S3_PRESIGNED_EXPIRATION=9999)
    def test_urls_tienen_vencimientos_independientes(self, crear):
        cliente = crear.return_value
        generar_urls_prefirmadas("archivo", "lote", 2)
        generar_url_descarga("archivo")
        generar_url_previsualizacion("archivo")
        llamadas = cliente.generate_presigned_url.call_args_list
        self.assertEqual([c.kwargs["ExpiresIn"] for c in llamadas], [3600, 3600, 300, 900])
        self.assertEqual([c.kwargs["ClientMethod"] for c in llamadas],
                         ["upload_part", "upload_part", "get_object", "get_object"])

    @patch("apps.archivos.services.storage.get_s3_client")
    def test_expiracion_explicita_sigue_funcionando(self, crear):
        generar_url_descarga("archivo", expiracion=60)
        self.assertEqual(crear.return_value.generate_presigned_url.call_args.kwargs["ExpiresIn"], 60)
        generar_url_previsualizacion("archivo", expiracion=120)
        self.assertEqual(crear.return_value.generate_presigned_url.call_args.kwargs["ExpiresIn"], 120)

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
