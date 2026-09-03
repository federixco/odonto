"""La portada es pública; rediseñar el acceso no altera las reglas de seguridad."""

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.enums import EstadoCuenta, RolUsuario


class LandingPublicaTests(SimpleTestCase):
    """SimpleTestCase impide consultas a la base en las visitas anónimas."""

    def test_portada_publica_y_enlaces_principales(self):
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/landing.html")
        for section in ("servicios", "nosotros", "contacto", "estudios"):
            self.assertContains(response, f'id="{section}"')
        self.assertContains(response, f'href="{reverse("login")}"')
        self.assertContains(response, "buen diagnóstico.")
        self.assertNotContains(response, 'name="password"')

    def test_archivos_estaticos_disponibles(self):
        for path in (
            "core/css/public.css", "core/js/public.js",
            "core/images/doc-isotipo.svg", "core/images/doc-equipo-original.jpg",
            "core/images/doc-radiografias.jpg", "core/images/doc-planificacion.png",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(finders.find(path))

    def test_portada_no_publica_archivos_clinicos(self):
        response = self.client.get(reverse("core:landing"))
        self.assertNotContains(response, 'src="/media/')
        self.assertNotContains(response, 'href="/media/')

    def test_paneles_continuan_protegidos(self):
        for name in ("dashboard_admin", "dashboard_odontologo", "dashboard_paciente", "odontologo_lista"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(
                    response, f'{reverse("login")}?next={reverse(name)}',
                    fetch_redirect_response=False,
                )

    def test_login_conserva_next_csrf_y_recuperacion(self):
        response = self.client.get(reverse("login"), {"next": reverse("dashboard_odontologo")})
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'name="next" value="/mi-consultorio/"')
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, f'href="{reverse("core:landing")}"')
        self.assertContains(response, f'href="{reverse("password_reset")}"')
        self.assertContains(response, f'href="{reverse("odontologo_autoregistro")}"')

    def test_login_rechaza_post_sin_csrf(self):
        response = Client(enforce_csrf_checks=True).post(reverse("login"), {})
        self.assertEqual(response.status_code, 403)


class LandingAutenticadaTests(TestCase):
    """Usuarios sintéticos únicamente en la base aislada del runner de pruebas."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="doc_landing_test", email="landing@example.com",
            password="Clave-Prueba-2026!", rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )

    def test_usuario_autenticado_tambien_ve_la_portada(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ir a mi cuenta")
        self.assertTemplateUsed(response, "core/landing.html")

    def test_login_respeta_destino_interno(self):
        response = self.client.post(reverse("login"), {
            "username": self.usuario.username, "password": "Clave-Prueba-2026!",
            "next": reverse("dashboard_odontologo"),
        })
        self.assertRedirects(response, reverse("dashboard_odontologo"))

    def test_login_no_redirige_a_dominio_externo(self):
        response = self.client.post(reverse("login"), {
            "username": self.usuario.username, "password": "Clave-Prueba-2026!",
            "next": "https://example.com/no-permitido",
        })
        self.assertRedirects(response, reverse("redireccion_roles"), fetch_redirect_response=False)

    def test_login_muestra_errores_sin_rellenar_password(self):
        response = self.client.post(reverse("login"), {
            "username": self.usuario.username, "password": "incorrecta-prueba",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertNotContains(response, 'value="incorrecta-prueba"')
