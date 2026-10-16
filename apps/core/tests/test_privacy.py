"""Contrato público y cookies reales, sin acceder a la base de datos."""

from django.conf import settings
from django.contrib.messages.storage.cookie import CookieStorage
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse

from apps.core.privacy import application_cookies


class PrivacyPublicTests(SimpleTestCase):
    def test_politica_publica_sin_datos_clinicos_ni_creacion_de_cookies(self):
        response = self.client.get(reverse("core:privacy"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/privacy.html")
        self.assertContains(response, '<h1>Política de Privacidad</h1>', html=True)
        self.assertContains(response, '<h2>Cookies</h2>', html=True)
        self.assertContains(response, 'datetime="2026-10-16"')
        self.assertContains(response, "16 de octubre de 2026")
        self.assertNotContains(response, 'src="/media/')
        self.assertNotContains(response, 'href="/media/')
        self.assertEqual(list(response.cookies), [])

    def test_politica_breve_institucional_sin_detalles_internos(self):
        response = self.client.get(reverse("core:privacy"))
        for text in ("Introducción", "Información que recopilamos", "Cómo utilizamos la información",
                     "Acceso a la información", "Estudios y archivos clínicos", "Seguridad y confidencialidad",
                     "Cookies", "Conservación de información", "Contacto", "doc.imagenes@gmail.com",
                     "no se utilizan cookies publicitarias ni de seguimiento comercial",
                     "D.O.C. aplica medidas técnicas y organizativas destinadas a proteger la información y limitar el acceso a usuarios autorizados."):
            with self.subTest(text=text):
                self.assertContains(response, text)
        for text in ("Django", "CSRF", "hash", "sessionid", "csrftoken", "S3", "MinIO",
                     "localStorage", "doc_cookie_notice_v1", "base de datos", "workers",
                     "Información por completar antes de producción", 'id="pendientes"',
                     "Google Analytics", "Rechazar todas", "Acepto la política", "cumple con el RGPD"):
            self.assertNotContains(response, text)
        self.assertNotIn("application_cookies", response.context)

    def test_links_y_aviso_en_landing_y_accesos_publicos(self):
        for name in ("core:landing", "core:privacy", "login", "odontologo_autoregistro",
                     "password_reset", "password_reset_done", "password_reset_complete"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'href="{reverse("core:privacy")}"')
                self.assertContains(response, f'href="{reverse("core:privacy")}#cookies-utilizadas"')
                self.assertContains(response, 'id="doc-cookie-notice"')
                self.assertContains(response, "Entendido")
                self.assertNotContains(response, 'aria-modal="true"')

    def test_creditos_tienen_un_punto_de_edicion_y_no_son_tarjetas(self):
        response = self.client.get(reverse("core:landing"))
        self.assertTemplateUsed(response, "core/includes/team_credits.html")
        self.assertContains(response, "Sistema desarrollado por")
        self.assertContains(response, '<span data-team-names>[NOMBRES DEL EQUIPO]</span>', html=True)

    def test_csrf_se_emite_sin_aceptar_aviso_y_se_sigue_exigiendo(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse("login"))
        self.assertIn(settings.CSRF_COOKIE_NAME, response.cookies)
        self.assertEqual(int(response.cookies[settings.CSRF_COOKIE_NAME]["max-age"]), settings.CSRF_COOKIE_AGE)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertEqual(client.post(reverse("login"), {}).status_code, 403)

    def test_cookie_messages_no_tiene_caducidad_persistente(self):
        from django.test import RequestFactory
        storage = CookieStorage(RequestFactory().get("/"))
        storage.add(20, "Aviso de prueba")
        response = HttpResponse()
        storage.update(response)
        cookie = response.cookies[storage.cookie_name]
        self.assertEqual(cookie["max-age"], "")
        self.assertEqual(cookie["expires"], "")

    @override_settings(SESSION_COOKIE_NAME="sesion_doc", SESSION_COOKIE_AGE=86400,
                       CSRF_COOKIE_NAME="csrf_doc", CSRF_COOKIE_AGE=172800)
    def test_descripcion_sigue_configuracion_sin_cambiar_autenticacion(self):
        cookies = application_cookies()
        self.assertEqual(cookies[0]["name"], "sesion_doc")
        self.assertIn("1 días", cookies[0]["duration"])
        self.assertEqual(cookies[1]["name"], "csrf_doc")
        self.assertIn("2 días", cookies[1]["duration"])

    @override_settings(CSRF_USE_SESSIONS=True, SESSION_EXPIRE_AT_BROWSER_CLOSE=True,
                       MESSAGE_STORAGE="django.contrib.messages.storage.session.SessionStorage")
    def test_no_enumera_cookies_que_configuracion_no_utiliza(self):
        cookies = application_cookies()
        self.assertEqual([row["name"] for row in cookies], [settings.SESSION_COOKIE_NAME])
        self.assertIn("cerrarlo", cookies[0]["duration"])

    def test_recursos_publicos_son_locales(self):
        for resource in ("core/css/privacy.css", "core/js/cookie_notice.js"):
            self.assertIsNotNone(finders.find(resource))
