from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.enums import EstadoCuenta, RolUsuario
from apps.pacientes.models import Paciente
from apps.usuarios.models import Usuario


class PacienteModelTests(TestCase):
    def test_rechaza_usuario_que_no_tiene_rol_paciente(self):
        odontologo = Usuario.objects.create_user(
            username="rol_incorrecto", email="rol.incorrecto@example.com",
            password="Clave-Prueba-2026!", rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        paciente = Paciente(
            usuario=odontologo, nombre="Ficha", apellido="Invalida", dni="34000000",
        )

        with self.assertRaises(ValidationError):
            paciente.full_clean()
