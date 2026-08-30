"""Pruebas de autorizaciones revocables."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.enums import EstadoAcceso, EstadoCuenta, RolUsuario
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo, Usuario

from apps.accesos.models import Autorizacion


class AutorizacionModelTests(TestCase):
    def setUp(self):
        self.administrador = Usuario.objects.create_superuser(
            username="administrador",
            email="admin@example.com",
            password="clave-segura",
        )
        cuenta_odontologo = Usuario.objects.create_user(
            username="derivante",
            email="derivante@example.com",
            password="clave-segura",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odontologo = Odontologo.objects.create(
            usuario=cuenta_odontologo,
            nombre="Ana",
            apellido="Pérez",
            matricula="MAT-001",
        )
        paciente = Paciente.objects.create(
            nombre="Juan",
            apellido="Gómez",
            dni="12345678",
        )
        self.estudio = Estudio.objects.create(
            paciente=paciente,
            tipo="Tomografía",
            fecha_estudio="2026-08-30",
        )

    def test_revocacion_conserva_fecha_y_administrador(self):
        autorizacion = Autorizacion.objects.create(
            odontologo=self.odontologo,
            estudio=self.estudio,
        )

        autorizacion.revocar(self.administrador)
        autorizacion.refresh_from_db()

        self.assertEqual(autorizacion.estado_acceso, EstadoAcceso.REVOCADO)
        self.assertIsNotNone(autorizacion.fecha_revocacion)
        self.assertEqual(autorizacion.revocado_por, self.administrador)
        self.assertFalse(autorizacion.esta_vigente())

    def test_solo_administrador_puede_revocar(self):
        autorizacion = Autorizacion.objects.create(
            odontologo=self.odontologo,
            estudio=self.estudio,
        )

        with self.assertRaises(ValidationError):
            autorizacion.revocar(self.odontologo.usuario)
