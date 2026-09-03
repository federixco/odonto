"""Pruebas del panel visual del centro, sobre la base aislada de Django."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.enums import EstadoCuenta, RolUsuario
from apps.usuarios.models import Odontologo


class PanelOdontologosPresentacionTests(TestCase):
    """El nuevo diseño mantiene rutas, validaciones y acciones protegidas."""

    @classmethod
    def setUpTestData(cls):
        cls.password = "Clave-Prueba-2026!"
        cls.admin = get_user_model().objects.create_user(
            username="admin_panel", email="admin@example.com", password=cls.password,
            rol=RolUsuario.ADMINISTRADOR, estado=EstadoCuenta.HABILITADA,
        )
        cls.profesional = get_user_model().objects.create_user(
            username="profesional_panel", email="profesional@example.com", password=cls.password,
            rol=RolUsuario.ODONTOLOGO, estado=EstadoCuenta.PENDIENTE,
        )
        cls.odontologo = Odontologo.objects.create(
            usuario=cls.profesional, nombre="Lucía", apellido="Prueba", matricula="QA-100",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def detail_url(self):
        return reverse("odontologo_detalle", args=[self.odontologo.pk])

    def edit_url(self):
        return reverse("odontologo_editar", args=[self.odontologo.pk])

    def pages(self):
        return [
            reverse("odontologo_lista"),
            reverse("odontologo_crear"), self.detail_url(), self.edit_url(),
        ]

    def test_todas_las_pantallas_comparten_marca_navegacion_y_css(self):
        for url in self.pages():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "core/admin_base.html")
                self.assertContains(response, "/static/core/css/public.css")
                self.assertContains(response, "/static/core/css/admin.css")
                self.assertContains(response, 'content="noindex, nofollow"')
                self.assertContains(response, f'action="{reverse("logout")}" method="post"')
                self.assertContains(response, "Cerrar sesión")
                self.assertNotContains(response, f'href="{reverse("dashboard_admin")}"')
                self.assertNotContains(response, "> Inicio</a>")

    def test_listado_muestra_datos_estado_y_acciones_reales(self):
        response = self.client.get(reverse("odontologo_lista"))
        for text in ("Prueba, Lucía", "QA-100", "profesional@example.com", "Pendiente", "1 resultado"):
            self.assertContains(response, text)
        self.assertContains(response, f'href="{self.detail_url()}"')
        self.assertContains(response, f'href="{self.edit_url()}"')
        self.assertContains(response, 'scope="col"')
        self.assertContains(response, 'aria-label="Buscar odontólogos"')

    def test_busqueda_conserva_consulta_y_ofrece_limpiar(self):
        response = self.client.get(reverse("odontologo_lista"), {"q": "QA-100"})
        self.assertContains(response, "Resultados de búsqueda")
        self.assertContains(response, 'value="QA-100"')
        self.assertContains(response, "Prueba, Lucía")
        self.assertContains(response, "Limpiar búsqueda")

    def test_busqueda_sin_resultados_y_contenido_escapado(self):
        query = '<script>alert("qa")</script>'
        response = self.client.get(reverse("odontologo_lista"), {"q": query})
        self.assertContains(response, "No encontramos coincidencias")
        self.assertContains(response, "0 resultados")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, query)
        self.assertNotContains(response, "Prueba, Lucía")

    def test_directorio_vacio_ofrece_alta(self):
        Odontologo.objects.all().delete()
        response = self.client.get(reverse("odontologo_lista"))
        self.assertContains(response, "Todavía no hay odontólogos registrados")
        self.assertContains(response, reverse("odontologo_crear"))

    def test_alta_muestra_campos_ayuda_y_habilitacion(self):
        response = self.client.get(reverse("odontologo_crear"))
        self.assertContains(response, "habilitada")
        for field in ("nombre", "apellido", "matricula", "telefono", "email", "username", "password", "password_confirm"):
            self.assertContains(response, f'name="{field}"')
        self.assertContains(response, 'autocomplete="new-password"')
        self.assertContains(response, 'aria-describedby="id_password_helptext"')
        self.assertContains(response, 'aria-label="Mostrar confirmar contraseña"')

    def test_alta_invalida_conserva_errores_y_no_crea_cuentas(self):
        count = get_user_model().objects.count()
        response = self.client.post(reverse("odontologo_crear"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, "Revisá los campos indicados")
        self.assertEqual(get_user_model().objects.count(), count)

    def test_edicion_no_expone_credenciales_y_rechaza_datos_invalidos(self):
        response = self.client.get(self.edit_url())
        self.assertContains(response, 'value="Lucía"')
        self.assertNotContains(response, 'name="password"')
        self.assertNotContains(response, 'name="username"')
        response = self.client.post(self.edit_url(), {"nombre": "No guardar", "email": "invalido"})
        self.assertContains(response, 'role="alert"')
        self.odontologo.refresh_from_db()
        self.assertEqual(self.odontologo.nombre, "Lucía")

    def test_edicion_valida_muestra_confirmacion_y_no_cambia_el_acceso(self):
        response = self.client.post(self.edit_url(), {
            "nombre": "Lucía", "apellido": "Actualizada", "matricula": "QA-100",
            "email": "actualizada@example.com", "telefono": "",
        }, follow=True)
        self.assertRedirects(response, self.detail_url())
        self.assertContains(response, "Datos de Actualizada, Lucía actualizados.")
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.estado, EstadoCuenta.PENDIENTE)
        self.assertTrue(self.profesional.check_password(self.password))

    def test_ficha_habilita_y_deshabilita_con_formularios_post(self):
        habilitar = reverse("odontologo_habilitar", args=[self.odontologo.pk])
        deshabilitar = reverse("odontologo_deshabilitar", args=[self.odontologo.pk])
        response = self.client.get(self.detail_url())
        self.assertContains(response, f'action="{habilitar}" method="post"')
        self.assertNotContains(response, f'action="{deshabilitar}"')
        response = self.client.post(habilitar, follow=True)
        self.assertContains(response, "Cuenta de Prueba, Lucía habilitada.")
        self.assertContains(response, f'action="{deshabilitar}" method="post"')
        self.assertContains(response, '<details class="access-caution">')
        response = self.client.post(deshabilitar, follow=True)
        self.assertContains(response, "Cuenta de Prueba, Lucía deshabilitada.")
        self.assertContains(response, f'action="{habilitar}" method="post"')
        self.profesional.refresh_from_db()
        self.assertFalse(self.profesional.is_active)

    def test_escrituras_requieren_csrf_y_cambios_de_estado_no_aceptan_get(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        state_urls = [reverse(name, args=[self.odontologo.pk]) for name in (
            "odontologo_habilitar", "odontologo_deshabilitar",
        )]
        for url in [reverse("odontologo_crear"), self.edit_url(), reverse("logout"), *state_urls]:
            with self.subTest(url=url):
                self.assertEqual(client.post(url, {}).status_code, 403)
        for url in state_urls:
            self.assertEqual(self.client.get(url).status_code, 405)
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.estado, EstadoCuenta.PENDIENTE)

    def test_anonimos_y_otros_roles_no_acceden_al_panel(self):
        self.client.logout()
        for url in [*self.pages(), reverse("dashboard_admin")]:
            self.assertEqual(self.client.get(url).status_code, 302)
        for role in (RolUsuario.ODONTOLOGO, RolUsuario.PACIENTE):
            account = get_user_model().objects.create_user(
                username=f"no_admin_{role}", email=f"{role.lower()}@example.com",
                password=self.password, rol=role, estado=EstadoCuenta.HABILITADA,
            )
            self.client.force_login(account)
            for url in [*self.pages(), reverse("dashboard_admin")]:
                with self.subTest(role=role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
            for url in [reverse("odontologo_crear"), self.edit_url(), *[
                reverse(name, args=[self.odontologo.pk]) for name in (
                    "odontologo_habilitar", "odontologo_deshabilitar",
                )
            ]]:
                with self.subTest(role=role, action=url):
                    self.assertEqual(self.client.post(url, {}).status_code, 403)
