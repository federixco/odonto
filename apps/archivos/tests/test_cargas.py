import json
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse

from apps.usuarios.models import Usuario
from apps.pacientes.models import Paciente
from apps.estudios.models import Estudio
from apps.archivos.models import Archivo
from apps.core.enums import RolUsuario, EstadoArchivo


class TestCargaArchivos(TestCase):
    def setUp(self):
        # Configurar Admin
        self.admin = Usuario.objects.create_user(
            username="admin1",
            email="admin@test.com",
            password="pwd",
            rol=RolUsuario.ADMINISTRADOR,
            estado="HABILITADA"
        )
        # Configurar Paciente y Odontologo (sin acceso a carga)
        self.paciente_user = Usuario.objects.create_user(
            username="paciente1",
            email="paciente@test.com",
            password="pwd",
            rol=RolUsuario.PACIENTE,
            estado="HABILITADA"
        )
        
        self.paciente = Paciente.objects.create(
            nombre="Juan",
            apellido="Perez",
            dni="12345678"
        )
        
        self.estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía",
            fecha_estudio="2026-09-01",
            estado="BORRADOR"
        )
        
        self.client = Client()

    def test_paciente_no_puede_iniciar_carga(self):
        """Prueba que un paciente recibe error 403 al intentar cargar."""
        self.client.force_login(self.paciente_user)
        url = reverse("archivo_iniciar", args=[self.estudio.pk])
        response = self.client.post(url, data=json.dumps({"nombre_archivo": "tomo.dcm", "formato": "DICOM", "tamano": 100}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    @patch("apps.archivos.views.iniciar_multipart_upload")
    @patch("apps.archivos.views.generar_urls_prefirmadas")
    def test_admin_puede_iniciar_carga(self, mock_generar, mock_iniciar):
        """Prueba que el admin recibe las urls generadas por boto3."""
        mock_iniciar.return_value = "fake_upload_id"
        mock_generar.return_value = [{"part_number": 1, "url": "http://fake/url"}]
        
        self.client.force_login(self.admin)
        url = reverse("archivo_iniciar", args=[self.estudio.pk])
        
        response = self.client.post(
            url,
            data=json.dumps({"nombre_archivo": "tomo.dcm", "formato": "DICOM", "tamano": 1024}),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["upload_id"], "fake_upload_id")
        self.assertEqual(len(data["partes"]), 1)
        
        # Verificar que se creó en la DB
        archivo = Archivo.objects.get(pk=data["archivo_id"])
        self.assertEqual(archivo.estado, EstadoArchivo.CARGANDO)
        self.assertTrue("tomo.dcm" in archivo.ruta_almacenamiento)
        
    @patch("apps.archivos.views.completar_multipart_upload")
    def test_completar_carga(self, mock_completar):
        mock_completar.return_value = {"tamano": 1024, "etag": "hash123"}
        
        archivo = Archivo.objects.create(
            estudio=self.estudio,
            nombre_archivo="tomo.dcm",
            formato="DICOM",
            categoria="DICOM",
            ruta_almacenamiento="estudios/x/y/tomo.dcm",
            tamano=100,
            upload_id="fake_upload_id",
            estado=EstadoArchivo.CARGANDO
        )
        
        self.client.force_login(self.admin)
        url = reverse("archivo_completar", args=[archivo.pk])
        
        response = self.client.post(
            url,
            data=json.dumps({"partes": [{"PartNumber": 1, "ETag": "hash123"}]}),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)
        archivo.refresh_from_db()
        self.assertEqual(archivo.estado, EstadoArchivo.COMPLETO)
        self.assertEqual(archivo.hash_sha256, "hash123")
        self.assertEqual(archivo.tamano, 1024)
