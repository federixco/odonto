"""Regresiones de la revisión del 29/09. No usan almacenamiento real."""

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


class RevisionPendientesTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            username="admin_revision", email="revision@example.test", password="clave-test",
        )
        self.paciente = Paciente.objects.create(nombre="Ana", apellido="Prueba", dni="30111222")
        self.lote = ImportacionEstudio.objects.create(
            iniciada_por=self.admin, nombre_carpeta="carpeta", cantidad_archivos=1,
            tamano_total=10, estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
        )
        self.archivo = Archivo.objects.create(
            importacion=self.lote, nombre_archivo="001.dcm", ruta_relativa="carpeta/001.dcm",
            formato=FormatoArchivo.DICOM, categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="pruebas/revision/001.dcm", tamano=10,
            estado=EstadoArchivo.COMPLETO,
        )
        self.client.force_login(self.admin)

    def registrar(self, datos):
        return self.client.post(
            reverse("importacion_registrar_paciente", args=[self.lote.pk]), datos,
        )

    def asociar_estudio(self):
        estudio = Estudio.objects.create(
            paciente=self.paciente, tipo="DICOM", fecha_estudio="2026-09-10",
        )
        self.archivo.estudio = estudio
        self.archivo.save(update_fields=["estudio"])
        return estudio

    def preparar_carga(self):
        self.lote.estado = EstadoImportacion.CARGANDO
        self.lote.save(update_fields=["estado"])
        self.archivo.estado = EstadoArchivo.CARGANDO
        self.archivo.upload_id = "multipart-test"
        self.archivo.save(update_fields=["estado", "upload_id"])

    def completar(self):
        return self.client.post(
            reverse("importacion_archivo_completar", args=[self.lote.pk, self.archivo.pk]),
            {"partes": [{"PartNumber": 1, "ETag": '"parte-test"'}], "carga_token": "multipart-test"},
            content_type="application/json",
        )

    def test_paciente_ya_seleccionado_redirige_sin_error_ni_duplicados(self):
        self.lote.paciente_sugerido = self.paciente
        self.lote.save(update_fields=["paciente_sugerido"])
        response = self.registrar({"dni": "otro"})
        self.assertRedirects(
            response, reverse("importacion_detalle", args=[self.lote.pk]),
            fetch_redirect_response=False,
        )
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.paciente_sugerido_id, self.paciente.pk)
        self.assertEqual(Paciente.objects.count(), 1)

    def test_dni_existente_selecciona_ficha_sin_crear_otra(self):
        response = self.registrar({"dni": self.paciente.dni})
        self.assertEqual(response.status_code, 302)
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.paciente_sugerido_id, self.paciente.pk)
        self.assertEqual(Paciente.objects.count(), 1)

    def test_nuevo_paciente_queda_seleccionado_sin_cuenta_web(self):
        response = self.registrar({"nombre": "Luis", "apellido": "Prueba", "dni": "32111222"})
        self.assertEqual(response.status_code, 302)
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.paciente_sugerido.dni, "32111222")
        self.assertIsNone(self.lote.paciente_sugerido.usuario_id)
        self.assertEqual(Paciente.objects.count(), 2)

    @patch("apps.estudios.views.eliminar_objeto", side_effect=RuntimeError("S3 no disponible"))
    @patch("apps.estudios.views.completar_multipart_upload", return_value={"tamano": 9})
    def test_error_de_limpieza_no_oculta_error_de_verificacion(self, completar, eliminar):
        self.preparar_carga()
        with self.assertLogs("apps.estudios.views", level="ERROR"):
            response = self.completar()
        self.assertEqual(response.status_code, 502)
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.estado, EstadoArchivo.INCORRECTO)
        self.assertIsNone(self.archivo.upload_id)
        eliminar.assert_called_once_with(self.archivo.ruta_almacenamiento)

    @patch("apps.estudios.views.abortar_multipart_upload", return_value=False)
    @patch("apps.estudios.views.completar_multipart_upload", side_effect=RuntimeError("Fallo multipart"))
    def test_aborto_no_confirmado_conserva_id_para_reconciliar(self, completar, abortar):
        self.preparar_carga()
        with self.assertLogs("apps.estudios.views", level="ERROR"):
            response = self.completar()
        self.assertEqual(response.status_code, 502)
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.estado, EstadoArchivo.INCORRECTO)
        self.assertEqual(self.archivo.upload_id, "multipart-test")

    @patch("apps.estudios.views.abortar_multipart_upload", side_effect=RuntimeError("Fallo aborto"))
    @patch("apps.estudios.views.completar_multipart_upload", side_effect=RuntimeError("Fallo multipart"))
    def test_excepcion_de_aborto_tambien_guarda_estado_incorrecto(self, completar, abortar):
        self.preparar_carga()
        with self.assertLogs("apps.estudios.views", level="ERROR"):
            response = self.completar()
        self.assertEqual(response.status_code, 502)
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.estado, EstadoArchivo.INCORRECTO)
        self.assertEqual(self.archivo.upload_id, "multipart-test")

    @patch("apps.estudios.views.abortar_multipart_upload", return_value=True)
    @patch("apps.estudios.views.completar_multipart_upload", side_effect=RuntimeError("Fallo multipart"))
    def test_aborto_confirmado_limpia_id(self, completar, abortar):
        self.preparar_carga()
        with self.assertLogs("apps.estudios.views", level="ERROR"):
            response = self.completar()
        self.assertEqual(response.status_code, 502)
        self.archivo.refresh_from_db()
        self.assertIsNone(self.archivo.upload_id)

    @patch("apps.archivos.views._marcar_incorrecto_y_revisar")
    def test_endpoint_compatibilidad_no_corrige_archivos_sin_estudio(self, corregir):
        response = self.client.post(reverse("archivo_eliminar", args=[self.archivo.pk]))
        self.assertEqual(response.status_code, 404)
        corregir.assert_not_called()
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.estado, EstadoArchivo.COMPLETO)

    def test_boton_zip_visible_con_una_sola_carpeta(self):
        estudio = self.asociar_estudio()
        response = self.client.get(reverse("estudio_detalle", args=[estudio.pk]))
        self.assertEqual(response.context["tree"]["nombre"], "carpeta")
        self.assertContains(response, reverse("estudio_descargar_completo", args=[estudio.pk]), count=1)

    def test_boton_zip_no_se_duplica_con_archivos_en_raiz(self):
        estudio = self.asociar_estudio()
        self.archivo.ruta_relativa = "001.dcm"
        self.archivo.save(update_fields=["ruta_relativa"])
        response = self.client.get(reverse("estudio_detalle", args=[estudio.pk]))
        self.assertEqual(response.context["tree"]["nombre"], "Raíz")
        self.assertContains(response, reverse("estudio_descargar_completo", args=[estudio.pk]), count=1)

    def test_sin_archivos_completos_no_se_ofrece_zip(self):
        estudio = self.asociar_estudio()
        self.archivo.estado = EstadoArchivo.INCORRECTO
        self.archivo.save(update_fields=["estado"])
        response = self.client.get(reverse("estudio_detalle", args=[estudio.pk]))
        self.assertNotContains(response, reverse("estudio_descargar_completo", args=[estudio.pk]))

    def test_estudio_eliminado_no_ofrece_zip(self):
        estudio = self.asociar_estudio()
        estudio.estado = EstadoEstudio.ELIMINADO
        estudio.save(update_fields=["estado"])
        response = self.client.get(reverse("estudio_detalle", args=[estudio.pk]))
        self.assertNotContains(response, reverse("estudio_descargar_completo", args=[estudio.pk]))

    def test_selector_compartido_en_ambas_variantes_de_confirmacion(self):
        for paciente_id in (None, self.paciente.pk):
            with self.subTest(paciente_id=paciente_id):
                self.lote.paciente_sugerido_id = paciente_id
                self.lote.save(update_fields=["paciente_sugerido"])
                response = self.client.get(reverse("importacion_detalle", args=[self.lote.pk]))
                self.assertContains(response, "data-paciente-selector", count=1)
                self.assertContains(response, "data-paciente-search", count=1)
                self.assertContains(response, "core/js/paciente_selector.js", count=1)
                self.assertNotContains(response, "filtrarPacientes(this)")

    def test_selector_escapa_nombres_no_confiables(self):
        self.paciente.nombre = '<img src=x onerror="alert(1)">'
        self.paciente.save(update_fields=["nombre"])
        response = self.client.get(reverse("importacion_detalle", args=[self.lote.pk]))
        self.assertContains(response, "selectores_remotos.js")
        self.assertNotContains(response, '<img src=x onerror="alert(1)">')

    def test_error_de_confirmacion_abre_selector_y_muestra_error(self):
        response = self.client.post(
            reverse("importacion_confirmar", args=[self.lote.pk]),
            {"paciente": "", "tipo": "DICOM", "fecha_estudio": "2026-09-10"},
        )
        self.assertContains(response, 'class="existing-patient-option" open')
        self.assertContains(response, "No pudimos confirmar el estudio.")
