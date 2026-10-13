"""Pruebas funcionales de los tableros de Odontólogo y Paciente (Etapa 4)."""

from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accesos.models import Autorizacion
from apps.core.enums import EstadoAcceso, EstadoCuenta, EstadoEstudio, RolUsuario
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo

User = get_user_model()


class TablerosEtapa4Tests(TestCase):
    def setUp(self):
        self.password = "Clave-Segura-2026!"

        # Odontólogo
        self.user_odon = User.objects.create_user(
            username="dr_perez",
            password=self.password,
            email="drperez@clinica.com",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odontologo = Odontologo.objects.create(
            usuario=self.user_odon,
            nombre="Carlos",
            apellido="Pérez",
            matricula="MP-8833",
        )

        # Paciente 1
        self.user_paciente1 = User.objects.create_user(
            username="paciente_uno",
            password=self.password,
            email="pac1@correo.com",
            rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente1 = Paciente.objects.create(
            usuario=self.user_paciente1,
            nombre="Lucas",
            apellido="Mendoza",
            dni="41000111",
            obra_social="OSDE",
        )

        # Paciente 2
        self.user_paciente2 = User.objects.create_user(
            username="paciente_dos",
            password=self.password,
            email="pac2@correo.com",
            rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente2 = Paciente.objects.create(
            usuario=self.user_paciente2,
            nombre="María",
            apellido="Ríos",
            dni="38000222",
        )

        # Estudios
        self.estudio1 = Estudio.objects.create(
            paciente=self.paciente1,
            tipo="Panorámica Digital",
            fecha_estudio=date(2026, 9, 10),
            estado=EstadoEstudio.PUBLICADO,
            fecha_publicacion=timezone.now(),
        )
        self.estudio2 = Estudio.objects.create(
            paciente=self.paciente2,
            tipo="Tomografía Cone Beam",
            fecha_estudio=date(2026, 9, 15),
            estado=EstadoEstudio.PUBLICADO,
            fecha_publicacion=timezone.now(),
        )

        # Autorizaciones para el odontólogo
        Autorizacion.objects.create(
            estudio=self.estudio1,
            odontologo=self.odontologo,
            estado_acceso=EstadoAcceso.VIGENTE,
        )
        Autorizacion.objects.create(
            estudio=self.estudio2,
            odontologo=self.odontologo,
            estado_acceso=EstadoAcceso.VIGENTE,
        )

    def test_dashboard_odontologo_muestra_metricas_y_estudios(self):
        self.client.login(username="dr_perez", password=self.password)
        resp = self.client.get(reverse("dashboard_odontologo"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "M.P. MP-8833")
        self.assertContains(resp, "Mendoza, Lucas")
        self.assertContains(resp, "Ríos, María")
        self.assertEqual(resp.context["total_estudios"], 2)
        self.assertEqual(resp.context["total_pacientes"], 2)

    def test_dashboard_odontologo_filtro_por_busqueda(self):
        self.client.login(username="dr_perez", password=self.password)
        # Búsqueda por DNI
        resp = self.client.get(reverse("dashboard_odontologo") + "?q=41000111")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mendoza, Lucas")
        self.assertNotContains(resp, "Ríos, María")

        # Búsqueda por apellido
        resp = self.client.get(reverse("dashboard_odontologo") + "?q=Ríos")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ríos, María")
        self.assertNotContains(resp, "Mendoza, Lucas")

    def test_dashboard_odontologo_filtro_por_tipo(self):
        self.client.login(username="dr_perez", password=self.password)
        resp = self.client.get(reverse("dashboard_odontologo") + "?tipo=Panorámica Digital")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mendoza, Lucas")
        self.assertNotContains(resp, "Ríos, María")

    def test_dashboard_odontologo_incluye_guia_tutorial(self):
        self.client.login(username="dr_perez", password=self.password)
        resp = self.client.get(reverse("dashboard_odontologo"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "id=\"btn-abrir-tutorial\"")
        self.assertContains(resp, "id=\"modal-tutorial-derivante\"")
        self.assertContains(resp, "Guía del Consultorio Virtual")
        self.assertContains(resp, "Búsqueda y Filtros de Pacientes")
        self.assertContains(resp, "Visor Diagnóstico Web 2D y 3D")
        self.assertContains(resp, "Descarga de Carpeta Completa (.ZIP)")
        self.assertContains(resp, "Privacidad y Permisos de Derivación")

    def test_dashboard_paciente_aislamiento(self):
        self.client.login(username="paciente_uno", password=self.password)
        resp = self.client.get(reverse("dashboard_paciente"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Lucas")
        self.assertContains(resp, "Panorámica Digital")
        # No debe ver estudios de María
        self.assertNotContains(resp, "Tomografía Cone Beam")


class NotificacionesAdminTests(TestCase):
    def setUp(self):
        self.password = "Clave-Segura-2026!"
        self.admin = User.objects.create_superuser(
            username="admin_test",
            password=self.password,
            email="admin@test.com",
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )

    def test_notificacion_admin_badge_muestra_odontologos_pendientes(self):
        self.client.login(username="admin_test", password=self.password)
        
        # Sin pendientes inicialmente
        resp = self.client.get(reverse("odontologo_lista"))
        self.assertEqual(resp.context["odontologos_pendientes_count"], 0)
        self.assertNotContains(resp, "admin-notification-badge")
        self.assertNotContains(resp, "admin-pending-pill")

        # Crear odontólogo pendiente
        user_pend = User.objects.create_user(
            username="odon_pend",
            password=self.password,
            email="pend@test.com",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.PENDIENTE,
        )
        Odontologo.objects.create(
            usuario=user_pend,
            nombre="Laura",
            apellido="Gómez",
            matricula="MP-9999",
        )

        resp = self.client.get(reverse("odontologo_lista"))
        self.assertEqual(resp.context["odontologos_pendientes_count"], 1)
        self.assertContains(resp, "admin-notification-badge")
        self.assertContains(resp, "admin-pending-pill")
        self.assertContains(resp, "<strong>1</strong> pendiente")

        # Habilitar el odontólogo
        user_pend.estado = EstadoCuenta.HABILITADA
        user_pend.save()

        resp = self.client.get(reverse("odontologo_lista"))
        self.assertEqual(resp.context["odontologos_pendientes_count"], 0)
        self.assertNotContains(resp, "admin-notification-badge")
        self.assertNotContains(resp, "admin-pending-pill")
