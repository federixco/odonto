"""Pruebas de integridad para cuentas y medios de contacto."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.enums import EstadoCuenta

from apps.usuarios.models import Usuario


class UsuarioModelTests(TestCase):
    def test_estado_controla_is_active(self):
        usuario = Usuario.objects.create_user(
            username="odontologo",
            email="odontologo@example.com",
            password="clave-segura",
            estado=EstadoCuenta.HABILITADA,
        )
        self.assertTrue(usuario.is_active)

        usuario.estado = EstadoCuenta.DESHABILITADA
        usuario.save()
        usuario.refresh_from_db()

        self.assertFalse(usuario.is_active)

    def test_telefono_puede_ser_unico_medio_de_contacto(self):
        usuario = Usuario(
            username="paciente",
            telefono="3704000000",
            estado=EstadoCuenta.PENDIENTE,
        )
        usuario.set_password("clave-segura")

        usuario.full_clean()
        usuario.save()

        self.assertIsNone(usuario.email)
        self.assertEqual(usuario.telefono, "3704000000")
        self.assertFalse(usuario.is_active)

    def test_exige_al_menos_un_medio_de_contacto(self):
        usuario = Usuario(username="sin-contacto")

        with self.assertRaises(ValidationError):
            usuario.full_clean()
