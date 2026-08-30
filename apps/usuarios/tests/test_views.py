from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.core.enums import EstadoCuenta, RolUsuario


User = get_user_model()


class AccesosRolesTestCase(TestCase):
    password = "Clave-Segura-2026!"

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_test",
            password=self.password,
            email="admin@test.com",
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odon_user = User.objects.create_user(
            username="odon_test",
            password=self.password,
            email="odon@test.com",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.pac_user = User.objects.create_user(
            username="pac_test",
            password=self.password,
            email="pac@test.com",
            rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )

    def test_acceso_anonimo_denegado(self):
        """Un usuario sin loguear es redirigido al login."""
        response = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_admin_accede_su_dashboard(self):
        self.client.login(username="admin_test", password=self.password)
        response = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usuarios/dashboard_admin.html")

    def test_admin_rechazado_en_dashboard_odontologo(self):
        """El administrador no debería acceder a vistas exclusivas de odontólogo."""
        self.client.login(username="admin_test", password=self.password)
        response = self.client.get(reverse("dashboard_odontologo"))
        self.assertEqual(response.status_code, 403)

    def test_odontologo_rechazado_en_dashboard_admin(self):
        self.client.login(username="odon_test", password=self.password)
        response = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(response.status_code, 403)

    def test_paciente_accede_su_dashboard(self):
        self.client.login(username="pac_test", password=self.password)
        response = self.client.get(reverse("dashboard_paciente"))
        self.assertEqual(response.status_code, 200)

    def test_login_real_redirige_segun_rol(self):
        """El formulario de login redirige al punto de entrada por roles."""
        response = self.client.post(
            reverse("login"),
            {"username": "odon_test", "password": self.password},
        )
        self.assertRedirects(
            response,
            reverse("redireccion_roles"),
            fetch_redirect_response=False,
        )

        response = self.client.get(reverse("redireccion_roles"))
        self.assertRedirects(response, reverse("dashboard_odontologo"))

    def test_usuario_deshabilitado_no_puede_iniciar_sesion(self):
        User.objects.create_user(
            username="deshabilitado",
            password=self.password,
            email="deshabilitado@test.com",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.DESHABILITADA,
        )

        response = self.client.post(
            reverse("login"),
            {"username": "deshabilitado", "password": self.password},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Por favor, introduzca un nombre de usuario")

    def test_logout_requiere_post_y_cierra_la_sesion(self):
        self.client.login(username="admin_test", password=self.password)

        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_recuperacion_envia_correo_sin_revelar_la_cuenta(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.odon_user.email},
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.odon_user.email])
        self.assertIn("Recuperación de acceso a SISETMA", mail.outbox[0].subject)
        self.assertIn("/auth/reset/", mail.outbox[0].body)

        response = self.client.post(
            reverse("password_reset"),
            {"email": "no-existe@test.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_politica_rechaza_contrasena_debil(self):
        with self.assertRaises(ValidationError):
            validate_password("123", user=self.odon_user)

    def test_enlace_principal_apunta_a_ruta_valida(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, f'href="{reverse("redireccion_roles")}"')
