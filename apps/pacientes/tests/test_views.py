"""Pruebas de ficha clínica, acceso excepcional y portal del paciente."""

from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.enums import EstadoCuenta, EstadoEstudio, RolUsuario
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Usuario


class PacientesViewsTests(TestCase):
    password = "Clave-Prueba-2026!"

    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin_pacientes", email="admin.pacientes@example.com",
            password=self.password, rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )
        self.usuario_paciente = Usuario.objects.create_user(
            username="paciente_portal", email="paciente.portal@example.com",
            password=self.password, rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente = Paciente.objects.create(
            usuario=self.usuario_paciente, nombre="Paula", apellido="Prueba", dni="33000001",
        )
        self.otro_paciente = Paciente.objects.create(
            nombre="Otra", apellido="Persona", dni="33000002",
        )
        self.publicado = Estudio.objects.create(
            paciente=self.paciente, tipo="Tomografía", fecha_estudio=date.today(),
            estado=EstadoEstudio.PUBLICADO, fecha_publicacion=timezone.now(),
        )
        self.borrador = Estudio.objects.create(
            paciente=self.paciente, tipo="Radiografía interna", fecha_estudio=date.today(),
            estado=EstadoEstudio.BORRADOR,
        )
        self.ajeno = Estudio.objects.create(
            paciente=self.otro_paciente, tipo="Estudio ajeno", fecha_estudio=date.today(),
            estado=EstadoEstudio.PUBLICADO, fecha_publicacion=timezone.now(),
        )

    def login_admin(self):
        self.client.force_login(self.admin)

    def test_administrador_crea_ficha_sin_cuenta(self):
        self.login_admin()
        response = self.client.post(reverse("paciente_crear"), {
            "nombre": "Lucía", "apellido": "Sin acceso", "dni": "33000003",
            "fecha_nacimiento": "", "obra_social": "", "usuario": "",
        })

        paciente = Paciente.objects.get(dni="33000003")
        self.assertRedirects(response, reverse("paciente_detalle", args=[paciente.pk]))
        self.assertIsNone(paciente.usuario)

    def test_solo_el_administrador_gestiona_fichas(self):
        response = self.client.get(reverse("paciente_lista"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.usuario_paciente)
        response = self.client.get(reverse("paciente_lista"))
        self.assertEqual(response.status_code, 403)

    def test_administrador_ve_listado_ficha_y_edicion(self):
        self.login_admin()

        for url in (
            reverse("paciente_lista"),
            reverse("paciente_detalle", args=[self.paciente.pk]),
            reverse("paciente_editar", args=[self.paciente.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "core/admin_base.html")

    def test_no_permita_vincular_una_cuenta_que_no_es_de_paciente(self):
        odontologo = Usuario.objects.create_user(
            username="odontologo_no_valido", email="odontologo.no.valido@example.com",
            password=self.password, rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.login_admin()
        response = self.client.post(reverse("paciente_crear"), {
            "nombre": "Cuenta", "apellido": "Incorrecta", "dni": "33000004",
            "fecha_nacimiento": "", "obra_social": "", "usuario": odontologo.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Paciente.objects.filter(dni="33000004").exists())
        self.assertContains(response, "opción válida")

    def test_administrador_crea_y_vincula_acceso_excepcional(self):
        paciente = Paciente.objects.create(nombre="Ana", apellido="Sin cuenta", dni="33000005")
        self.login_admin()
        response = self.client.post(reverse("paciente_acceso_crear", args=[paciente.pk]), {
            "username": "ana_paciente", "email": "ana.paciente@example.com", "telefono": "",
            "password": self.password, "password_confirm": self.password,
        })

        paciente.refresh_from_db()
        self.assertRedirects(response, reverse("paciente_detalle", args=[paciente.pk]))
        self.assertEqual(paciente.usuario.rol, RolUsuario.PACIENTE)
        self.assertEqual(paciente.usuario.estado, EstadoCuenta.HABILITADA)

    def test_paciente_solo_ve_sus_estudios_publicados(self):
        self.client.force_login(self.usuario_paciente)
        response = self.client.get(reverse("dashboard_paciente"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.publicado.tipo)
        self.assertNotContains(response, self.borrador.tipo)
        self.assertNotContains(response, self.ajeno.tipo)
        self.assertNotContains(response, "Descargar")

    def test_cuenta_paciente_sin_ficha_no_accede_al_portal(self):
        sin_ficha = Usuario.objects.create_user(
            username="sin_ficha", email="sin.ficha@example.com", password=self.password,
            rol=RolUsuario.PACIENTE, estado=EstadoCuenta.HABILITADA,
        )
        self.client.force_login(sin_ficha)

        response = self.client.get(reverse("dashboard_paciente"))

        self.assertEqual(response.status_code, 403)
