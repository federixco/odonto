from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.core.enums import EstadoCuenta, RolUsuario


User = get_user_model()


class AccesosRolesTestCase(TestCase):
    def setUp(self):
        # Crear usuario Administrador
        self.admin_user = User.objects.create_user(
            username="admin_test", password="123", email="admin@test.com",
            rol=RolUsuario.ADMINISTRADOR, estado=EstadoCuenta.HABILITADA
        )
        
        # Crear usuario Odontólogo
        self.odon_user = User.objects.create_user(
            username="odon_test", password="123", email="odon@test.com",
            rol=RolUsuario.ODONTOLOGO, estado=EstadoCuenta.HABILITADA
        )
        
        # Crear usuario Paciente
        self.pac_user = User.objects.create_user(
            username="pac_test", password="123", email="pac@test.com",
            rol=RolUsuario.PACIENTE, estado=EstadoCuenta.HABILITADA
        )

    def test_acceso_anonimo_denegado(self):
        """Un usuario sin loguear es redirigido al login."""
        response = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_admin_accede_su_dashboard(self):
        self.client.login(username="admin_test", password="123")
        response = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usuarios/dashboard_admin.html")

    def test_admin_rechazado_en_dashboard_odontologo(self):
        """El administrador no debería acceder a vistas exclusivas de odontólogo."""
        self.client.login(username="admin_test", password="123")
        response = self.client.get(reverse("dashboard_odontologo"))
        self.assertEqual(response.status_code, 403) # Forbidden

    def test_odontologo_rechazado_en_dashboard_admin(self):
        self.client.login(username="odon_test", password="123")
        response = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(response.status_code, 403) # Forbidden

    def test_paciente_accede_su_dashboard(self):
        self.client.login(username="pac_test", password="123")
        response = self.client.get(reverse("dashboard_paciente"))
        self.assertEqual(response.status_code, 200)

    def test_redireccion_login(self):
        """El login debe redirigir al panel correcto según el rol."""
        self.client.login(username="odon_test", password="123")
        response = self.client.get(reverse("redireccion_roles"))
        self.assertRedirects(response, reverse("dashboard_odontologo"))
