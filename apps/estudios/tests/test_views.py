"""Pruebas del inicio administrativo de un estudio."""

from django.test import TestCase
from django.urls import reverse

from apps.core.enums import EstadoCuenta, EstadoEstudio, RolUsuario
from apps.pacientes.models import Paciente
from apps.usuarios.models import Usuario

from ..models import Estudio


class EstudioViewsTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin_estudios",
            email="admin.estudios@example.com",
            password="Clave-Segura-2026!",
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odontologo = Usuario.objects.create_user(
            username="odontologo_estudios",
            email="odontologo.estudios@example.com",
            password="Clave-Segura-2026!",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente = Paciente.objects.create(
            nombre="María",
            apellido="Gómez",
            dni="30111222",
        )

    def test_administrador_puede_abrir_formulario(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("estudio_crear"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preparar un")

    def test_odontologo_no_puede_crear_estudio(self):
        self.client.force_login(self.odontologo)
        response = self.client.get(reverse("estudio_crear"))
        self.assertEqual(response.status_code, 403)

    def test_creacion_conserva_borrador_y_redirige_a_carga(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("estudio_crear"),
            {
                "paciente": self.paciente.pk,
                "tipo": "Tomografía 3D",
                "fecha_estudio": "2026-09-08",
                "observaciones": "Prueba sin datos clínicos reales.",
            },
        )
        estudio = Estudio.objects.get()
        self.assertEqual(estudio.estado, EstadoEstudio.BORRADOR)
        self.assertRedirects(response, reverse("estudio_detalle", args=[estudio.pk]))
