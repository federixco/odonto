"""Pruebas de seguridad del comando de limpieza de desarrollo."""

from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.archivos.models import Archivo
from apps.core.enums import CategoriaArchivo, EstadoArchivo, EstadoCuenta, FormatoArchivo, RolUsuario
from apps.estudios.models import ImportacionEstudio
from apps.usuarios.models import Usuario


@override_settings(DEBUG=True)
class LimpiarImportacionesPruebaTests(TestCase):
    def setUp(self):
        admin = Usuario.objects.create_user(
            username="admin_limpieza",
            email="limpieza@example.com",
            password="clave-segura",
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )
        importacion = ImportacionEstudio.objects.create(
            iniciada_por=admin,
            nombre_carpeta="prueba_limpieza",
            cantidad_archivos=1,
            tamano_total=100,
        )
        Archivo.objects.create(
            importacion=importacion,
            nombre_archivo="001",
            ruta_relativa="prueba/001",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="importaciones/prueba/001",
            tamano=100,
            estado=EstadoArchivo.COMPLETO,
        )

    def test_sin_confirmar_solo_muestra_vista_previa(self):
        call_command("limpiar_importaciones_prueba")

        self.assertEqual(ImportacionEstudio.objects.count(), 1)
        self.assertEqual(Archivo.objects.count(), 1)

    @patch(
        "apps.estudios.management.commands.limpiar_importaciones_prueba.get_s3_client"
    )
    def test_confirmado_limpia_storage_y_base(self, get_s3_client):
        get_s3_client.return_value.delete_objects.return_value = {}

        call_command("limpiar_importaciones_prueba", confirmar=True)

        self.assertEqual(ImportacionEstudio.objects.count(), 0)
        self.assertEqual(Archivo.objects.count(), 0)
        get_s3_client.return_value.delete_objects.assert_called_once()

    @override_settings(AWS_S3_ENDPOINT_URL="https://storage.example.test")
    @patch("apps.estudios.management.commands.limpiar_importaciones_prueba.get_s3_client")
    def test_rechaza_storage_remoto_aun_con_debug(self, cliente):
        with self.assertRaises(CommandError):
            call_command("limpiar_importaciones_prueba", confirmar=True)
        cliente.assert_not_called()
        self.assertEqual(Archivo.objects.count(), 1)

    @patch("apps.estudios.management.commands.limpiar_importaciones_prueba.abortar_multipart_upload", return_value=False)
    @patch("apps.estudios.management.commands.limpiar_importaciones_prueba.get_s3_client")
    def test_aborto_fallido_preserva_fila_para_reintento(self, cliente, abortar):
        Archivo.objects.update(upload_id="upload-ficticio", estado=EstadoArchivo.CARGANDO)
        with self.assertRaises(CommandError):
            call_command("limpiar_importaciones_prueba", confirmar=True)
        abortar.assert_called_once()
        cliente.assert_not_called()
        self.assertEqual(Archivo.objects.count(), 1)
