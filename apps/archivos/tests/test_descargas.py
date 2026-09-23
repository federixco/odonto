"""Pruebas de descarga segura y previsualización de archivos (Etapa 4)."""

from datetime import date
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accesos.models import Autorizacion
from apps.archivos.models import Archivo
from apps.auditoria.models import LogActividad
from apps.core.enums import (
    CategoriaArchivo,
    EstadoAcceso,
    EstadoArchivo,
    EstadoCuenta,
    EstadoEstudio,
    FormatoArchivo,
    RolUsuario,
    TipoEvento,
)
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo

User = get_user_model()


class DescargasYPrevisualizacionTests(TestCase):
    def setUp(self):
        self.password = "Clave-Segura-2026!"
        
        # Administrador
        self.admin = User.objects.create_user(
            username="admin_doc",
            password=self.password,
            email="admin@doc.com",
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )

        # Odontólogo autorizado
        self.user_odon = User.objects.create_user(
            username="odon_doc",
            password=self.password,
            email="odon@doc.com",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odontologo = Odontologo.objects.create(
            usuario=self.user_odon,
            nombre="Carlos",
            apellido="Pérez",
            matricula="MN12345",
        )

        # Odontólogo no autorizado
        self.user_odon_ajeno = User.objects.create_user(
            username="odon_ajeno",
            password=self.password,
            email="ajeno@doc.com",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odontologo_ajeno = Odontologo.objects.create(
            usuario=self.user_odon_ajeno,
            nombre="Esteban",
            apellido="Gómez",
            matricula="MN99999",
        )

        # Paciente titular
        self.user_paciente = User.objects.create_user(
            username="paciente_doc",
            password=self.password,
            email="paciente@doc.com",
            rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente = Paciente.objects.create(
            usuario=self.user_paciente,
            nombre="Ana",
            apellido="García",
            dni="40111222",
            fecha_nacimiento=date(1995, 5, 20),
        )

        # Paciente ajeno
        self.user_paciente_ajeno = User.objects.create_user(
            username="paciente_ajeno",
            password=self.password,
            email="ajeno_pac@doc.com",
            rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente_ajeno = Paciente.objects.create(
            usuario=self.user_paciente_ajeno,
            nombre="Roberto",
            apellido="Díaz",
            dni="35999888",
        )

        # Estudio publicado
        self.estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="CBCT Tomografía",
            fecha_estudio=date.today(),
            estado=EstadoEstudio.PUBLICADO,
            fecha_publicacion=timezone.now(),
        )

        # Autorización vigente para odontólogo
        self.autorizacion = Autorizacion.objects.create(
            estudio=self.estudio,
            odontologo=self.odontologo,
            estado_acceso=EstadoAcceso.VIGENTE,
        )

        # Archivos: uno PDF (previsualizable) y uno DICOM (no previsualizable directamente)
        self.archivo_pdf = Archivo.objects.create(
            estudio=self.estudio,
            nombre_archivo="informe_clinico.pdf",
            ruta_relativa="informe_clinico.pdf",
            formato=FormatoArchivo.PDF,
            categoria=CategoriaArchivo.IMAGEN_DOCUMENTO,
            ruta_almacenamiento="estudios/1/informe.pdf",
            tamano=102400,
            content_type="application/pdf",
            estado=EstadoArchivo.COMPLETO,
        )
        self.archivo_dcm = Archivo.objects.create(
            estudio=self.estudio,
            nombre_archivo="tomografia.dcm",
            ruta_relativa="tomografia.dcm",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="estudios/1/tomografia.dcm",
            tamano=5242880,
            content_type="application/dicom",
            estado=EstadoArchivo.COMPLETO,
        )

    def test_descarga_requiere_autenticacion(self):
        url = reverse("archivo_descargar", args=[self.archivo_dcm.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("login"), resp.url)

    def test_paciente_tiene_bloqueada_la_descarga(self):
        self.client.login(username="paciente_doc", password=self.password)
        url = reverse("archivo_descargar", args=[self.archivo_dcm.pk])
        resp = self.client.get(url)
        # Debe responder 403 Forbidden por PermissionDenied
        self.assertEqual(resp.status_code, 403)

    def test_odontologo_no_autorizado_bloqueado(self):
        self.client.login(username="odon_ajeno", password=self.password)
        url = reverse("archivo_descargar", args=[self.archivo_dcm.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    @patch("apps.archivos.views.generar_url_descarga")
    def test_odontologo_autorizado_puede_descargar_y_audita(self, mock_generar):
        mock_generar.return_value = "http://s3.doc.local/presigned-download-url"
        self.client.login(username="odon_doc", password=self.password)

        url = reverse("archivo_descargar", args=[self.archivo_dcm.pk])
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "http://s3.doc.local/presigned-download-url")

        # Verificar auditoría
        log = LogActividad.objects.filter(
            estudio=self.estudio,
            usuario=self.user_odon,
            tipo_evento=TipoEvento.DESCARGA,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("tomografia.dcm", log.detalles)

    def test_previsualizacion_archivo_no_compatible_da_404(self):
        self.client.login(username="paciente_doc", password=self.password)
        url = reverse("archivo_previsualizar", args=[self.archivo_dcm.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    @patch("apps.archivos.views.generar_url_previsualizacion")
    def test_paciente_puede_previsualizar_pdf_propio(self, mock_previs):
        mock_previs.return_value = "http://s3.doc.local/presigned-inline-pdf"
        self.client.login(username="paciente_doc", password=self.password)

        url = reverse("archivo_previsualizar", args=[self.archivo_pdf.pk])
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "http://s3.doc.local/presigned-inline-pdf")

        # Verificar auditoría
        log = LogActividad.objects.filter(
            estudio=self.estudio,
            usuario=self.user_paciente,
            tipo_evento=TipoEvento.VISUALIZACION,
        ).first()
        self.assertIsNotNone(log)

    def test_paciente_no_puede_previsualizar_estudios_ajenos(self):
        self.client.login(username="paciente_ajeno", password=self.password)
        url = reverse("archivo_previsualizar", args=[self.archivo_pdf.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
