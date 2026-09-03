"""El diseño público conserva validación, habilitación y recuperación de Django."""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.core.enums import EstadoCuenta, RolUsuario


class FormulariosPublicosPresentacionTests(SimpleTestCase):
    """Las páginas iniciales no necesitan consultar cuentas de la base de datos."""

    def test_registro_muestra_marca_campos_y_habilitacion(self):
        response = self.client.get(reverse("odontologo_autoregistro"))
        self.assertTemplateUsed(response, "core/auth_base.html")
        self.assertContains(response, "Creá tu cuenta profesional")
        self.assertContains(response, "pendiente de habilitación")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        for value in ("given-name", "family-name", "email", "tel", "username", "new-password"):
            self.assertContains(response, f'autocomplete="{value}"')
        self.assertContains(response, 'id="id_password_helptext"')
        self.assertContains(response, 'aria-describedby="id_password_helptext"')
        self.assertContains(response, 'aria-label="Mostrar confirmar contraseña"')

    def test_paginas_recuperacion_comparten_diseno_y_enlaces(self):
        for name in ("password_reset", "password_reset_done", "password_reset_complete"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "core/auth_base.html")
                self.assertContains(response, '/static/core/css/public.css')
                self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')
                self.assertContains(response, f'href="{reverse("login")}"')

    def test_registro_y_recuperacion_siguen_exigiendo_csrf(self):
        for name in ("odontologo_autoregistro", "password_reset"):
            with self.subTest(name=name):
                response = Client(enforce_csrf_checks=True).post(reverse(name), {})
                self.assertEqual(response.status_code, 403)


class FormulariosPublicosFlujoTests(TestCase):
    """Flujos reales contra SQLite de pruebas, nunca contra cuentas de la vista previa."""

    password = "Acceso-Prueba-2026!"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="profesional_qa", email="profesional@example.com",
            password=self.password, rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )

    def reset_url(self):
        return reverse("password_reset_confirm", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(self.user.pk)),
            "token": default_token_generator.make_token(self.user),
        })

    def test_registro_invalido_muestra_errores_sin_crear_cuenta(self):
        response = self.client.post(reverse("odontologo_autoregistro"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, 'Revisá los campos indicados')
        self.assertTemplateUsed(response, "core/auth_base.html")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_registro_valido_mantiene_cuenta_pendiente(self):
        response = self.client.post(reverse("odontologo_autoregistro"), {
            "username": "registro_qa", "email": "registro@example.com",
            "nombre": "Laura", "apellido": "Prueba", "matricula": "QA-001",
            "password": self.password, "password_confirm": self.password,
        }, follow=True)
        self.assertRedirects(response, reverse("login"))
        self.assertContains(response, "Un administrador debe habilitarla")
        user = get_user_model().objects.get(username="registro_qa")
        self.assertEqual(user.estado, EstadoCuenta.PENDIENTE)
        self.assertFalse(user.is_active)
        self.assertFalse(self.client.login(username=user.username, password=self.password))

    def test_recuperacion_da_confirmacion_generica_para_cualquier_correo(self):
        for email in (self.user.email, "desconocido@example.com"):
            response = self.client.post(reverse("password_reset"), {"email": email}, follow=True)
            self.assertRedirects(response, reverse("password_reset_done"))
            self.assertContains(response, "Si el correo corresponde a una cuenta habilitada")
            self.assertTemplateUsed(response, "core/auth_base.html")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_nueva_contrasena_completa_flujo_y_no_permite_reutilizar_enlace(self):
        token_url = self.reset_url()
        response = self.client.get(token_url, follow=True)
        self.assertTrue(response.context["validlink"])
        self.assertTemplateUsed(response, "core/auth_base.html")
        self.assertContains(response, 'autocomplete="new-password"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'Repetí la nueva contraseña que escribiste arriba.')
        form_url = response.redirect_chain[-1][0]
        new_password = "Nueva-Clave-Segura-2026!"
        response = self.client.post(form_url, {
            "new_password1": new_password, "new_password2": new_password,
        }, follow=True)
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.assertContains(response, "Tu contraseña está actualizada")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password(self.password))
        response = self.client.get(token_url, follow=True)
        self.assertFalse(response.context["validlink"])
        self.assertContains(response, "Este enlace ya no está disponible")

    def test_enlace_invalido_ofrece_solicitar_otro(self):
        url = reverse("password_reset_confirm", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(self.user.pk)), "token": "no-valido",
        })
        response = self.client.get(url)
        self.assertFalse(response.context["validlink"])
        self.assertContains(response, "Tu contraseña no se modificó")
        self.assertContains(response, f'href="{reverse("password_reset")}"')
        self.assertNotContains(response, 'name="new_password1"')

    def test_nueva_contrasena_invalida_conserva_errores_y_clave_anterior(self):
        response = self.client.get(self.reset_url(), follow=True)
        form_url = response.redirect_chain[-1][0]
        response = self.client.post(form_url, {"new_password1": "123", "new_password2": "456"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, 'Revisá los campos indicados')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        self.assertNotContains(response, 'value="123"')
