"""Pruebas del control de acceso por objeto para estudios."""

from datetime import date

from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone
from django.views.generic import DetailView

from apps.accesos.models import Autorizacion
from apps.core.enums import EstadoCuenta, EstadoEstudio, RolUsuario
from apps.core.mixins import EstudioAccesoMixin
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo, Usuario


class EstudioProtegidoView(EstudioAccesoMixin, DetailView):
    """Vista mínima para ejercitar el mixin sin depender de etapas posteriores."""

    model = Estudio

    def render_to_response(self, context, **response_kwargs):
        return HttpResponse("estudio permitido", **response_kwargs)


urlpatterns = [
    path("auth/", include("django.contrib.auth.urls")),
    path(
        "estudios/<int:pk>/",
        EstudioProtegidoView.as_view(),
        name="estudio_protegido",
    ),
]


@override_settings(ROOT_URLCONF=__name__)
class EstudioAccesoMixinTests(TestCase):
    password = "Clave-Segura-2026!"

    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin_objeto",
            password=self.password,
            email="admin.objeto@test.com",
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )
        self.usuario_odontologo = Usuario.objects.create_user(
            username="odontologo_objeto",
            password=self.password,
            email="odontologo.objeto@test.com",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odontologo = Odontologo.objects.create(
            usuario=self.usuario_odontologo,
            nombre="Ana",
            apellido="Derivante",
            matricula="MAT-OBJ-1",
        )
        self.usuario_paciente = Usuario.objects.create_user(
            username="paciente_objeto",
            password=self.password,
            email="paciente.objeto@test.com",
            rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente = Paciente.objects.create(
            usuario=self.usuario_paciente,
            nombre="Pedro",
            apellido="Paciente",
            dni="30000001",
        )
        self.otro_paciente = Paciente.objects.create(
            nombre="Otra",
            apellido="Persona",
            dni="30000002",
        )
        self.publicado = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía",
            fecha_estudio=date.today(),
            estado=EstadoEstudio.PUBLICADO,
            fecha_publicacion=timezone.now(),
        )
        self.borrador = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Radiografía",
            fecha_estudio=date.today(),
            estado=EstadoEstudio.BORRADOR,
        )
        self.eliminado = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Modelo 3D",
            fecha_estudio=date.today(),
            estado=EstadoEstudio.ELIMINADO,
        )
        self.estudio_ajeno = Estudio.objects.create(
            paciente=self.otro_paciente,
            tipo="Tomografía",
            fecha_estudio=date.today(),
            estado=EstadoEstudio.PUBLICADO,
            fecha_publicacion=timezone.now(),
        )
        self.autorizacion = Autorizacion.objects.create(
            odontologo=self.odontologo,
            estudio=self.publicado,
        )
        Autorizacion.objects.create(
            odontologo=self.odontologo,
            estudio=self.borrador,
        )

    def obtener(self, usuario, estudio):
        self.client.force_login(usuario)
        return self.client.get(reverse("estudio_protegido", args=[estudio.pk]))

    def test_anonimo_es_redirigido_al_login(self):
        response = self.client.get(
            reverse("estudio_protegido", args=[self.publicado.pk])
        )

        self.assertEqual(response.status_code, 302)

    def test_administrador_accede_a_cualquier_estado(self):
        self.assertEqual(self.obtener(self.admin, self.eliminado).status_code, 200)

    def test_odontologo_accede_a_publicado_con_autorizacion_vigente(self):
        response = self.obtener(self.usuario_odontologo, self.publicado)

        self.assertEqual(response.status_code, 200)

    def test_odontologo_no_accede_a_borrador_aunque_este_autorizado(self):
        response = self.obtener(self.usuario_odontologo, self.borrador)

        self.assertEqual(response.status_code, 403)

    def test_odontologo_no_accede_con_autorizacion_revocada(self):
        self.autorizacion.revocar(self.admin)

        response = self.obtener(self.usuario_odontologo, self.publicado)

        self.assertEqual(response.status_code, 403)

    def test_paciente_solo_accede_a_estudios_propios_publicados(self):
        self.assertEqual(
            self.obtener(self.usuario_paciente, self.publicado).status_code,
            200,
        )
        self.assertEqual(
            self.obtener(self.usuario_paciente, self.borrador).status_code,
            403,
        )
        self.assertEqual(
            self.obtener(self.usuario_paciente, self.eliminado).status_code,
            403,
        )
        self.assertEqual(
            self.obtener(self.usuario_paciente, self.estudio_ajeno).status_code,
            403,
        )
