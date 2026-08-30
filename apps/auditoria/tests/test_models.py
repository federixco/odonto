"""Pruebas de inmutabilidad de la auditoría."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.enums import TipoEvento
from apps.usuarios.models import Usuario

from apps.auditoria.models import LogActividad


class LogActividadModelTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_superuser(
            username="administrador",
            email="admin@example.com",
            password="clave-segura",
        )

    def test_registro_creado_no_puede_modificarse(self):
        registro = LogActividad.objects.create(
            usuario=self.usuario,
            tipo_evento=TipoEvento.NOTIFICACION,
            resultado="Correo enviado",
        )
        registro.resultado = "Resultado alterado"

        with self.assertRaises(ValidationError):
            registro.save()

    def test_registro_no_puede_eliminarse(self):
        registro = LogActividad.objects.create(
            usuario=self.usuario,
            tipo_evento=TipoEvento.INICIO_SESION,
            resultado="Correcto",
        )

        with self.assertRaises(ValidationError):
            registro.delete()

        with self.assertRaises(ValidationError):
            LogActividad.objects.filter(pk=registro.pk).delete()

    def test_usuario_es_obligatorio(self):
        registro = LogActividad(
            tipo_evento=TipoEvento.CARGA,
            resultado="Carga iniciada",
        )

        with self.assertRaises(ValidationError):
            registro.save()
