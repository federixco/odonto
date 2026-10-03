"""Ubicación y colisiones de los reemplazos, con S3 simulado."""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.archivos.models import Archivo
from apps.core.enums import (
    CategoriaArchivo, EstadoArchivo, EstadoEstudio, EstadoImportacion, FormatoArchivo,
)
from apps.estudios.models import Estudio, ImportacionEstudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Usuario


class RutasReemplazoTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            username="admin_rutas", email="rutas@example.test", password="clave-test",
        )
        paciente = Paciente.objects.create(nombre="Ana", apellido="Prueba", dni="30111222")
        self.estudio = Estudio.objects.create(
            paciente=paciente, tipo="DICOM", fecha_estudio="2026-09-10",
            estado=EstadoEstudio.EN_REVISION,
        )
        self.lote = ImportacionEstudio.objects.create(
            iniciada_por=self.admin, estudio=self.estudio, nombre_carpeta="exportacion",
            cantidad_archivos=1, tamano_total=10, estado=EstadoImportacion.CONFIRMADA,
        )
        self.anterior = Archivo.objects.create(
            estudio=self.estudio, importacion=self.lote, nombre_archivo="informe.pdf",
            ruta_relativa="exportacion/informes/informe.pdf", formato=FormatoArchivo.PDF,
            categoria=CategoriaArchivo.IMAGEN_DOCUMENTO, ruta_almacenamiento="pruebas/anterior.pdf",
            tamano=10, estado=EstadoArchivo.INCORRECTO,
        )
        self.client.force_login(self.admin)

    def iniciar(self, nombre="corregido.pdf"):
        return self.client.post(
            reverse("archivo_iniciar", args=[self.estudio.pk]),
            {"nombre_archivo": nombre, "tamano": 10, "archivo_reemplazado": self.anterior.pk},
            content_type="application/json",
        )

    def crear_colision(self, ruta="exportacion/informes/corregido.pdf", estado=EstadoArchivo.COMPLETO):
        return Archivo.objects.create(
            estudio=self.estudio, nombre_archivo="corregido.pdf", ruta_relativa=ruta,
            formato=FormatoArchivo.PDF, categoria=CategoriaArchivo.IMAGEN_DOCUMENTO,
            ruta_almacenamiento="pruebas/colision.pdf", tamano=10, estado=estado,
        )

    @patch("apps.archivos.views.generar_urls_prefirmadas", return_value=[])
    @patch("apps.archivos.views.iniciar_multipart_upload", return_value="upload-reemplazo")
    def test_reemplazo_hereda_carpeta_sin_duplicar_ruta_del_lote(self, iniciar, firmar):
        response = self.iniciar()
        self.assertEqual(response.status_code, 200)
        nuevo = Archivo.objects.get(pk=response.json()["archivo_id"])
        self.assertEqual(nuevo.ruta_relativa, "exportacion/informes/corregido.pdf")
        self.assertEqual(nuevo.nombre_archivo, "corregido.pdf")
        self.assertEqual(nuevo.archivo_reemplazado_id, self.anterior.pk)
        self.assertIsNone(nuevo.importacion_id)
        self.anterior.refresh_from_db()
        self.assertEqual(self.anterior.ruta_relativa, "exportacion/informes/informe.pdf")
        self.assertEqual(self.anterior.importacion_id, self.lote.pk)

    @patch("apps.archivos.views.generar_urls_prefirmadas", return_value=[])
    @patch("apps.archivos.views.iniciar_multipart_upload", return_value="upload-reemplazo")
    def test_mismo_nombre_conserva_ruta_original(self, iniciar, firmar):
        response = self.iniciar("informe.pdf")
        self.assertEqual(response.status_code, 200)
        nuevo = Archivo.objects.get(pk=response.json()["archivo_id"])
        self.assertEqual(nuevo.ruta_relativa, self.anterior.ruta_relativa)
        self.assertIsNone(nuevo.importacion_id)

    @patch("apps.archivos.views.iniciar_multipart_upload")
    def test_rechaza_colisiones_con_archivos_vigentes_antes_de_s3(self, iniciar):
        for estado in (EstadoArchivo.COMPLETO, EstadoArchivo.CARGANDO):
            with self.subTest(estado=estado):
                colision = self.crear_colision(estado=estado)
                response = self.iniciar()
                self.assertEqual(response.status_code, 409)
                iniciar.assert_not_called()
                colision.delete()

    @patch("apps.archivos.views.iniciar_multipart_upload")
    def test_ruta_raiz_detecta_colision_con_archivo_sin_ruta(self, iniciar):
        self.anterior.ruta_relativa = "informe.pdf"
        self.anterior.save(update_fields=["ruta_relativa"])
        self.crear_colision(ruta="")
        self.assertEqual(self.iniciar().status_code, 409)
        iniciar.assert_not_called()

    @patch("apps.archivos.views.iniciar_multipart_upload")
    def test_rechaza_ruta_demasiado_larga_antes_de_s3(self, iniciar):
        self.anterior.ruta_relativa = "a" * 490 + "/x.pdf"
        self.anterior.save(update_fields=["ruta_relativa"])
        self.assertEqual(self.iniciar().status_code, 400)
        iniciar.assert_not_called()
