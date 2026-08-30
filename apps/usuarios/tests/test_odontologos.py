"""Tests para gestión de cuentas de odontólogos derivantes."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.enums import EstadoCuenta, RolUsuario
from apps.usuarios.models import Odontologo

User = get_user_model()


class GestionOdontologosTestCase(TestCase):
    """Pruebas de alta, autorregistro, habilitación y restricción de acceso."""

    def setUp(self):
        self.password = "Clave-Segura-2026!"

        # Admin habilitado
        self.admin = User.objects.create_user(
            username="admin_test", password=self.password,
            email="admin@test.com", rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )

        # Odontólogo habilitado existente
        self.odon_user = User.objects.create_user(
            username="odon_existente", password=self.password,
            email="odon@test.com", rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odontologo = Odontologo.objects.create(
            usuario=self.odon_user, nombre="Juan", apellido="Perez",
            matricula="MAT-001",
        )

    # --- Test: Admin crea odontólogo con estado HABILITADA ---

    def test_admin_crea_odontologo_habilitado(self):
        self.client.login(username="admin_test", password=self.password)
        response = self.client.post(reverse("odontologo_crear"), {
            "username": "nuevo_odon",
            "email": "nuevo@test.com",
            "password": self.password,
            "password_confirm": self.password,
            "nombre": "Carlos",
            "apellido": "Lopez",
            "matricula": "MAT-002",
        })
        self.assertRedirects(response, reverse("odontologo_lista"))

        nuevo = Odontologo.objects.get(matricula="MAT-002")
        self.assertEqual(nuevo.usuario.estado, EstadoCuenta.HABILITADA)
        self.assertTrue(nuevo.usuario.is_active)

    # --- Test: Autorregistro crea con estado PENDIENTE ---

    def test_autoregistro_crea_cuenta_pendiente(self):
        response = self.client.post(reverse("odontologo_autoregistro"), {
            "username": "auto_odon",
            "email": "auto@test.com",
            "password": self.password,
            "password_confirm": self.password,
            "nombre": "Maria",
            "apellido": "Gomez",
            "matricula": "MAT-003",
        })
        self.assertRedirects(response, reverse("login"))

        nuevo = Odontologo.objects.get(matricula="MAT-003")
        self.assertEqual(nuevo.usuario.estado, EstadoCuenta.PENDIENTE)
        self.assertFalse(nuevo.usuario.is_active)

    # --- Test: Cuenta PENDIENTE no puede loguearse ---

    def test_cuenta_pendiente_no_puede_loguearse(self):
        # Crear cuenta pendiente
        self.client.post(reverse("odontologo_autoregistro"), {
            "username": "pendiente_odon",
            "email": "pendiente@test.com",
            "password": self.password,
            "password_confirm": self.password,
            "nombre": "Pedro",
            "apellido": "Ruiz",
            "matricula": "MAT-004",
        })

        # Intentar login
        login_ok = self.client.login(username="pendiente_odon", password=self.password)
        self.assertFalse(login_ok)

    # --- Test: Admin habilita cuenta PENDIENTE → puede loguearse ---

    def test_admin_habilita_cuenta_pendiente(self):
        # Crear cuenta pendiente
        pendiente_user = User.objects.create_user(
            username="pendiente2", password=self.password,
            email="pend2@test.com", rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.PENDIENTE,
        )
        odon_pend = Odontologo.objects.create(
            usuario=pendiente_user, nombre="Ana", apellido="Diaz",
            matricula="MAT-005",
        )

        # Admin habilita
        self.client.login(username="admin_test", password=self.password)
        response = self.client.post(reverse("odontologo_habilitar", args=[odon_pend.pk]))
        self.assertRedirects(response, reverse("odontologo_detalle", args=[odon_pend.pk]))

        pendiente_user.refresh_from_db()
        self.assertEqual(pendiente_user.estado, EstadoCuenta.HABILITADA)
        self.assertTrue(pendiente_user.is_active)

        # Ahora sí puede loguearse
        self.client.logout()
        login_ok = self.client.login(username="pendiente2", password=self.password)
        self.assertTrue(login_ok)

    # --- Test: Admin deshabilita cuenta → no puede loguearse ---

    def test_admin_deshabilita_cuenta(self):
        self.client.login(username="admin_test", password=self.password)
        response = self.client.post(reverse("odontologo_deshabilitar", args=[self.odontologo.pk]))
        self.assertRedirects(response, reverse("odontologo_detalle", args=[self.odontologo.pk]))

        self.odon_user.refresh_from_db()
        self.assertEqual(self.odon_user.estado, EstadoCuenta.DESHABILITADA)
        self.assertFalse(self.odon_user.is_active)

        # Intento de login falla
        self.client.logout()
        login_ok = self.client.login(username="odon_existente", password=self.password)
        self.assertFalse(login_ok)

    # --- Test: Odontólogo NO accede a vistas de admin ---

    def test_odontologo_no_accede_a_gestion(self):
        self.client.login(username="odon_existente", password=self.password)

        response = self.client.get(reverse("odontologo_lista"))
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse("odontologo_crear"))
        self.assertEqual(response.status_code, 403)

    # --- Test: Listado filtra por búsqueda ---

    def test_listado_busca_por_matricula(self):
        self.client.login(username="admin_test", password=self.password)

        response = self.client.get(reverse("odontologo_lista"), {"q": "MAT-001"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perez")

        response = self.client.get(reverse("odontologo_lista"), {"q": "inexistente"})
        self.assertNotContains(response, "Perez")
