"""Verificación de privacidad con proveedor simulado, sin datos clínicos reales."""

from io import StringIO
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.archivos.models import Archivo
from apps.core.enums import CategoriaArchivo, EstadoArchivo, FormatoArchivo
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente


def denegacion(status=403):
    return ClientError({
        "Error": {"Code": "AccessDenied" if status == 403 else "NotFound", "Message": "ficticio"},
        "ResponseMetadata": {"HTTPStatusCode": status},
    }, "operacion")


@override_settings(AWS_S3_ENDPOINT_URL="https://storage.example.test")
class PrivacidadStorageTests(TestCase):
    def setUp(self):
        paciente = Paciente.objects.create(nombre="Prueba", apellido="Ficticia", dni="12345678")
        estudio = Estudio.objects.create(paciente=paciente, tipo="Prueba", fecha_estudio="2026-10-04")
        self.archivo = Archivo.objects.create(
            estudio=estudio, nombre_archivo="prueba.dcm", formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM, ruta_almacenamiento="prueba/objeto",
            tamano=100, estado=EstadoArchivo.COMPLETO,
        )
        self.privado = Mock()
        self.anonimo = Mock()
        self.anonimo.list_objects_v2.side_effect = denegacion()
        self.anonimo.get_object.side_effect = denegacion()
        self.salida = StringIO()
        parche = patch(
            "apps.archivos.management.commands.verificar_almacenamiento_privado.get_s3_client",
            side_effect=[self.privado, self.anonimo],
        )
        self.crear = parche.start()
        self.addCleanup(parche.stop)

    def ejecutar(self):
        call_command("verificar_almacenamiento_privado", archivo_id=self.archivo.pk, stdout=self.salida)

    def test_rechazo_anonimo_sin_escrituras(self):
        self.ejecutar()
        self.assertIn("No sustituye", self.salida.getvalue())
        self.assertEqual(self.crear.call_args_list[1].kwargs, {"anonimo": True})
        self.anonimo.get_object.assert_called_once_with(
            Bucket="unit-tests-no-real-storage", Key="prueba/objeto", Range="bytes=0-0",
        )
        for cliente in (self.privado, self.anonimo):
            cliente.close.assert_called_once()
            cliente.put_object.assert_not_called()
            cliente.delete_object.assert_not_called()
        self.assertEqual(Archivo.objects.count(), 1)

    def test_listado_publico_falla(self):
        self.anonimo.list_objects_v2.side_effect = None
        self.anonimo.list_objects_v2.return_value = {}
        with self.assertRaisesRegex(CommandError, "listar"):
            self.ejecutar()
        self.anonimo.get_object.assert_not_called()
        self.anonimo.close.assert_called_once()

    def test_lectura_publica_falla_y_cierra_cuerpo(self):
        self.anonimo.get_object.side_effect = None
        cuerpo = Mock()
        self.anonimo.get_object.return_value = {"Body": cuerpo}
        with self.assertRaisesRegex(CommandError, "lectura anónima"):
            self.ejecutar()
        cuerpo.close.assert_called_once()
        cuerpo.read.assert_not_called()

    def test_404_no_se_considera_privado(self):
        self.anonimo.get_object.side_effect = denegacion(404)
        with self.assertRaisesRegex(CommandError, "inconclusa"):
            self.ejecutar()

    def test_error_proveedor_no_expone_secretos(self):
        self.privado.head_object.side_effect = RuntimeError("https://storage/?token=secreto-ficticio")
        with self.assertRaises(CommandError) as error:
            self.ejecutar()
        self.assertNotIn("secreto-ficticio", str(error.exception) + self.salida.getvalue())
        self.privado.close.assert_called_once()

    @override_settings(AWS_S3_ENDPOINT_URL="http://127.0.0.1:9000")
    def test_http_no_contacta_proveedor(self):
        with self.assertRaisesRegex(CommandError, "HTTPS"):
            self.ejecutar()
        self.crear.assert_not_called()

    def test_archivo_inexistente_no_contacta_proveedor(self):
        with self.assertRaisesRegex(CommandError, "archivo completo"):
            call_command("verificar_almacenamiento_privado", archivo_id=999999)
        self.crear.assert_not_called()
