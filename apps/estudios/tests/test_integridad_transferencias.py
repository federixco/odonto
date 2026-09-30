"""Regresiones de reconfirmación y rollback de cargas; usan S3 simulado."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.archivos.models import Archivo
from apps.auditoria.models import LogActividad
from apps.core.enums import (
    CategoriaArchivo, EstadoArchivo, EstadoImportacion, FormatoArchivo, TipoEvento,
)
from apps.estudios.models import Estudio, ImportacionEstudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Usuario


class IntegridadTransferenciasTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            username="admin_transferencias", email="transferencias@example.test", password="clave-test",
        )
        self.paciente = Paciente.objects.create(nombre="Paciente", apellido="Prueba", dni="12345678")
        self.lote = ImportacionEstudio.objects.create(
            iniciada_por=self.admin, nombre_carpeta="carpeta", cantidad_archivos=1,
            tamano_total=10, estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
        )
        self.archivo = Archivo.objects.create(
            importacion=self.lote, nombre_archivo="001.dcm", ruta_relativa="carpeta/001.dcm",
            formato=FormatoArchivo.DICOM, categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="importaciones/test/001.dcm", tamano=10, estado=EstadoArchivo.COMPLETO,
        )
        self.datos = {"paciente": self.paciente.pk, "tipo": "DICOM", "fecha_estudio": "2026-09-10"}
        self.client.force_login(self.admin)

    def test_reconfirmar_no_crea_otro_estudio_ni_mueve_archivos(self):
        url = reverse("importacion_confirmar", args=[self.lote.pk])
        primera = self.client.post(url, self.datos)
        self.assertEqual(primera.status_code, 302)
        estudio = Estudio.objects.get()
        segunda = self.client.post(url, self.datos)
        self.assertEqual(segunda.status_code, 409)
        self.archivo.refresh_from_db()
        self.lote.refresh_from_db()
        self.assertEqual(Estudio.objects.count(), 1)
        self.assertEqual(self.archivo.estudio_id, estudio.pk)
        self.assertEqual(self.lote.estudio_id, estudio.pk)
        self.assertEqual(self.lote.estado, EstadoImportacion.CONFIRMADA)
        self.assertEqual(LogActividad.objects.filter(tipo_evento=TipoEvento.IMPORTACION_CONFIRMADA).count(), 1)

    @patch("apps.estudios.views.analizar_importacion")
    def test_reanalizar_confirmada_no_altera_estado_ni_archivos(self, analizar):
        self.client.post(reverse("importacion_confirmar", args=[self.lote.pk]), self.datos)
        estudio = Estudio.objects.get()
        response = self.client.post(reverse("importacion_analizar", args=[self.lote.pk]))
        self.assertEqual(response.status_code, 409)
        analizar.assert_not_called()
        self.lote.refresh_from_db()
        self.archivo.refresh_from_db()
        self.assertEqual(self.lote.estado, EstadoImportacion.CONFIRMADA)
        self.assertEqual(self.lote.estudio_id, estudio.pk)
        self.assertEqual(self.archivo.estudio_id, estudio.pk)

    def test_instancia_antigua_no_puede_reconfirmar(self):
        instancia_antigua = ImportacionEstudio.objects.get(pk=self.lote.pk)
        self.client.post(reverse("importacion_confirmar", args=[self.lote.pk]), self.datos)
        original = Estudio.objects.get()
        otro = Estudio.objects.create(paciente=self.paciente, tipo="DICOM", fecha_estudio="2026-09-10")
        with self.assertRaises(ValidationError):
            instancia_antigua.confirmar(otro)
        with self.assertRaises(ValidationError):
            instancia_antigua.marcar_procesando()
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.estudio_id, original.pk)

    @patch("apps.estudios.views.analizar_importacion")
    def test_no_admite_otro_analisis_mientras_esta_procesando(self, analizar):
        self.lote.estado = EstadoImportacion.CARGANDO
        self.lote.save(update_fields=["estado"])
        self.lote.marcar_procesando()
        response = self.client.post(reverse("importacion_analizar", args=[self.lote.pk]))
        self.assertEqual(response.status_code, 409)
        analizar.assert_not_called()
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.estado, EstadoImportacion.PROCESANDO)

    @patch("apps.estudios.views.analizar_importacion")
    def test_reintento_de_analisis_desde_error_sigue_disponible(self, analizar):
        self.lote.estado = EstadoImportacion.ERROR
        self.lote.save(update_fields=["estado"])

        def completar(lote):
            lote.marcar_pendiente_confirmacion()
            return lote

        analizar.side_effect = completar
        response = self.client.post(reverse("importacion_analizar", args=[self.lote.pk]))
        self.assertEqual(response.status_code, 200)
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.estado, EstadoImportacion.PENDIENTE_CONFIRMACION)

    def test_no_crea_estudio_si_la_importacion_esta_incompleta(self):
        self.archivo.estado = EstadoArchivo.CARGANDO
        self.archivo.save(update_fields=["estado"])
        response = self.client.post(reverse("importacion_confirmar", args=[self.lote.pk]), self.datos)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Estudio.objects.exists())

    @patch("apps.estudios.views.abortar_multipart_upload", return_value=True)
    @patch("apps.estudios.views.generar_urls_prefirmadas")
    @patch("apps.estudios.views.iniciar_multipart_upload", return_value="upload-simulado")
    def test_fallo_de_firma_revierte_fila_y_permite_reintentar_ruta(self, iniciar, firmar, abortar):
        self.lote.estado = EstadoImportacion.CARGANDO
        self.lote.save(update_fields=["estado"])
        url = reverse("importacion_archivo_iniciar", args=[self.lote.pk])
        datos = {"ruta_relativa": "carpeta/otro.dcm", "tamano": 10}
        firmar.side_effect = RuntimeError("Fallo de firma simulado")
        with self.assertLogs("apps.estudios.views", level="ERROR"):
            response = self.client.post(url, datos, content_type="application/json")
        self.assertEqual(response.status_code, 502)
        self.assertFalse(self.lote.archivos.filter(ruta_relativa=datos["ruta_relativa"]).exists())
        abortar.assert_called_once()
        self.assertEqual(abortar.call_args.args[1], "upload-simulado")
        firmar.side_effect = None
        firmar.return_value = [{"part_number": 1, "url": "https://storage.example.test/parte"}]
        response = self.client.post(url, datos, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.lote.archivos.filter(ruta_relativa=datos["ruta_relativa"]).count(), 1)

    @patch("apps.estudios.views.abortar_multipart_upload", return_value=True)
    @patch("apps.estudios.views.generar_urls_prefirmadas")
    @patch("apps.estudios.views.iniciar_multipart_upload", return_value="otro-upload")
    def test_intento_duplicado_no_borra_archivo_existente(self, iniciar, firmar, abortar):
        self.lote.estado = EstadoImportacion.CARGANDO
        self.lote.save(update_fields=["estado"])
        with self.assertLogs("apps.estudios.views", level="ERROR"):
            response = self.client.post(
                reverse("importacion_archivo_iniciar", args=[self.lote.pk]),
                {"ruta_relativa": self.archivo.ruta_relativa, "tamano": 10}, content_type="application/json",
            )
        self.assertEqual(response.status_code, 502)
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.estado, EstadoArchivo.COMPLETO)
        self.assertEqual(self.lote.archivos.count(), 1)
        firmar.assert_not_called()
        abortar.assert_called_once()
