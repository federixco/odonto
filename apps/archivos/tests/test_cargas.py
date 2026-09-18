"""Pruebas del coordinador HTTP de cargas multipartes."""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

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
from apps.accesos.models import Autorizacion
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo, Usuario

from ..models import Archivo


@override_settings(
    S3_MULTIPART_PART_SIZE=5 * 1024 * 1024,
    S3_MAX_UPLOAD_SIZE=20 * 1024 * 1024,
)
class CargaArchivosTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin_carga",
            email="admin.carga@example.com",
            password="Clave-Segura-2026!",
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente_user = Usuario.objects.create_user(
            username="paciente_carga",
            email="paciente.carga@example.com",
            password="Clave-Segura-2026!",
            rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente = Paciente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            dni="12345678",
        )
        self.estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía",
            fecha_estudio="2026-09-01",
        )

    def post_json(self, url, data):
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )

    def crear_archivo_cargando(self, **cambios):
        datos = {
            "estudio": self.estudio,
            "nombre_archivo": "tomografia.dcm",
            "formato": FormatoArchivo.DICOM,
            "categoria": CategoriaArchivo.DICOM,
            "ruta_almacenamiento": "estudios/1/archivos/archivo.dcm",
            "tamano": 1024,
            "upload_id": "upload-prueba",
            "cantidad_partes": 1,
            "estado": EstadoArchivo.CARGANDO,
        }
        datos.update(cambios)
        return Archivo.objects.create(**datos)

    def test_solo_el_administrador_puede_iniciar_carga(self):
        self.client.force_login(self.paciente_user)
        response = self.post_json(
            reverse("archivo_iniciar", args=[self.estudio.pk]),
            {"nombre_archivo": "tomografia.dcm", "tamano": 1024},
        )
        self.assertEqual(response.status_code, 403)

    @patch("apps.archivos.views.generar_urls_prefirmadas")
    @patch("apps.archivos.views.iniciar_multipart_upload")
    def test_backend_deriva_formato_categoria_y_partes(self, iniciar, generar):
        iniciar.return_value = "upload-prueba"
        generar.return_value = [{"part_number": 1, "url": "https://storage/parte"}]
        self.client.force_login(self.admin)

        response = self.post_json(
            reverse("archivo_iniciar", args=[self.estudio.pk]),
            {"nombre_archivo": "tomografia.dcm", "tamano": 1024},
        )

        self.assertEqual(response.status_code, 200)
        archivo = Archivo.objects.get(pk=response.json()["archivo_id"])
        self.assertEqual(archivo.formato, FormatoArchivo.DICOM)
        self.assertEqual(archivo.categoria, CategoriaArchivo.DICOM)
        self.assertEqual(archivo.cantidad_partes, 1)
        self.assertNotIn("tomografia", archivo.ruta_almacenamiento)
        self.assertNotIn("upload_id", response.json())

    @patch("apps.archivos.views.iniciar_multipart_upload")
    def test_rechaza_formato_no_permitido_sin_contactar_s3(self, iniciar):
        self.client.force_login(self.admin)
        response = self.post_json(
            reverse("archivo_iniciar", args=[self.estudio.pk]),
            {"nombre_archivo": "programa.exe", "tamano": 1024},
        )
        self.assertEqual(response.status_code, 400)
        iniciar.assert_not_called()
        self.assertFalse(Archivo.objects.exists())

    @patch("apps.archivos.views.logger.exception")
    @patch("apps.archivos.views.abortar_multipart_upload")
    @patch("apps.archivos.views.generar_urls_prefirmadas")
    @patch("apps.archivos.views.iniciar_multipart_upload")
    def test_aborta_s3_si_falla_la_generacion_de_urls(
        self, iniciar, generar, abortar, registrar_error
    ):
        iniciar.return_value = "upload-prueba"
        generar.side_effect = RuntimeError("fallo interno")
        self.client.force_login(self.admin)

        response = self.post_json(
            reverse("archivo_iniciar", args=[self.estudio.pk]),
            {"nombre_archivo": "tomografia.dcm", "tamano": 1024},
        )

        self.assertEqual(response.status_code, 502)
        self.assertNotContains(response, "fallo interno", status_code=502)
        abortar.assert_called_once()
        registrar_error.assert_called_once()
        archivo = Archivo.objects.get()
        self.assertEqual(archivo.estado, EstadoArchivo.INCORRECTO)
        self.assertIsNone(archivo.upload_id)

    @patch("apps.archivos.views.calcular_sha256_objeto")
    @patch("apps.archivos.views.completar_multipart_upload")
    def test_completa_con_sha256_real_y_registra_auditoria(self, completar, calcular):
        archivo = self.crear_archivo_cargando()
        completar.return_value = {"tamano": 1024, "etag": "etag-multipartes"}
        calcular.return_value = "a" * 64
        self.client.force_login(self.admin)

        response = self.post_json(
            reverse("archivo_completar", args=[archivo.pk]),
            {"partes": [{"PartNumber": 1, "ETag": '"etag-parte"'}]},
        )

        self.assertEqual(response.status_code, 200)
        archivo.refresh_from_db()
        self.assertEqual(archivo.estado, EstadoArchivo.COMPLETO)
        self.assertEqual(archivo.hash_sha256, "a" * 64)
        self.assertIsNone(archivo.upload_id)
        self.assertTrue(
            LogActividad.objects.filter(
                usuario=self.admin,
                estudio=self.estudio,
                tipo_evento=TipoEvento.CARGA,
            ).exists()
        )

    @patch("apps.archivos.views.eliminar_objeto")
    @patch("apps.archivos.views.completar_multipart_upload")
    def test_descarta_objeto_si_el_tamano_no_coincide(self, completar, eliminar):
        archivo = self.crear_archivo_cargando(tamano=1024)
        completar.return_value = {"tamano": 512, "etag": "etag"}
        self.client.force_login(self.admin)

        response = self.post_json(
            reverse("archivo_completar", args=[archivo.pk]),
            {"partes": [{"PartNumber": 1, "ETag": '"etag-parte"'}]},
        )

        self.assertEqual(response.status_code, 400)
        eliminar.assert_called_once_with(archivo.ruta_almacenamiento)
        archivo.refresh_from_db()
        self.assertEqual(archivo.estado, EstadoArchivo.INCORRECTO)

    @patch("apps.archivos.views.completar_multipart_upload")
    def test_no_acepta_partes_faltantes_o_repetidas(self, completar):
        archivo = self.crear_archivo_cargando(cantidad_partes=2)
        self.client.force_login(self.admin)
        response = self.post_json(
            reverse("archivo_completar", args=[archivo.pk]),
            {
                "partes": [
                    {"PartNumber": 1, "ETag": '"a"'},
                    {"PartNumber": 1, "ETag": '"b"'},
                ]
            },
        )
        self.assertEqual(response.status_code, 400)
        completar.assert_not_called()

    @patch("apps.archivos.views.abortar_multipart_upload", return_value=True)
    def test_cancelacion_marca_el_archivo_como_incorrecto(self, abortar):
        archivo = self.crear_archivo_cargando()
        self.client.force_login(self.admin)
        response = self.client.post(reverse("archivo_cancelar", args=[archivo.pk]))
        self.assertEqual(response.status_code, 200)
        abortar.assert_called_once()
        archivo.refresh_from_db()
        self.assertEqual(archivo.estado, EstadoArchivo.INCORRECTO)
        self.assertIsNone(archivo.upload_id)

    @patch("apps.archivos.views.eliminar_objeto")
    def test_marcar_incorrecto_revoca_acceso_sin_borrar_el_objeto(self, eliminar):
        cuenta = Usuario.objects.create_user(
            username="derivante_correccion",
            email="derivante.correccion@example.com",
            password="Clave-Segura-2026!",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        odontologo = Odontologo.objects.create(
            usuario=cuenta,
            nombre="Ana",
            apellido="Derivante",
            matricula="MP-CORR-1",
        )
        autorizacion = Autorizacion.objects.create(
            estudio=self.estudio,
            odontologo=odontologo,
        )
        archivo = self.crear_archivo_cargando(
            estado=EstadoArchivo.COMPLETO,
            upload_id=None,
            hash_sha256="c" * 64,
        )
        self.estudio.estado = EstadoEstudio.PUBLICADO
        self.estudio.fecha_publicacion = "2026-09-01T12:00:00Z"
        self.estudio.save(update_fields=["estado", "fecha_publicacion"])
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("archivo_marcar_incorrecto", args=[archivo.pk])
        )

        self.assertRedirects(
            response,
            reverse("estudio_detalle", args=[self.estudio.pk]),
        )
        archivo.refresh_from_db()
        self.estudio.refresh_from_db()
        autorizacion.refresh_from_db()
        self.assertEqual(archivo.estado, EstadoArchivo.INCORRECTO)
        self.assertEqual(self.estudio.estado, EstadoEstudio.EN_REVISION)
        self.assertEqual(autorizacion.estado_acceso, EstadoAcceso.REVOCADO)
        self.assertEqual(autorizacion.revocado_por, self.admin)
        eliminar.assert_not_called()
        self.assertTrue(
            LogActividad.objects.filter(
                estudio=self.estudio,
                tipo_evento=TipoEvento.CORRECCION,
            ).exists()
        )

    @patch("apps.archivos.views.calcular_sha256_objeto")
    @patch("apps.archivos.views.completar_multipart_upload")
    @patch("apps.archivos.views.generar_urls_prefirmadas")
    @patch("apps.archivos.views.iniciar_multipart_upload")
    def test_reemplazo_completado_conserva_ambas_versiones(
        self,
        iniciar,
        generar,
        completar,
        calcular,
    ):
        anterior = self.crear_archivo_cargando(
            estado=EstadoArchivo.INCORRECTO,
            upload_id=None,
            hash_sha256="d" * 64,
        )
        self.estudio.estado = EstadoEstudio.EN_REVISION
        self.estudio.save(update_fields=["estado"])
        iniciar.return_value = "upload-reemplazo"
        generar.return_value = [{"part_number": 1, "url": "https://storage/parte"}]
        completar.return_value = {"tamano": 1024, "etag": "etag-reemplazo"}
        calcular.return_value = "e" * 64
        self.client.force_login(self.admin)

        iniciar_response = self.post_json(
            reverse("archivo_iniciar", args=[self.estudio.pk]),
            {
                "nombre_archivo": "tomografia-corregida.dcm",
                "tamano": 1024,
                "archivo_reemplazado": anterior.pk,
            },
        )
        self.assertEqual(iniciar_response.status_code, 200)
        nuevo = Archivo.objects.get(pk=iniciar_response.json()["archivo_id"])

        completar_response = self.post_json(
            reverse("archivo_completar", args=[nuevo.pk]),
            {"partes": [{"PartNumber": 1, "ETag": '"etag-parte"'}]},
        )

        self.assertEqual(completar_response.status_code, 200)
        anterior.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertEqual(anterior.estado, EstadoArchivo.REEMPLAZADO)
        self.assertEqual(nuevo.estado, EstadoArchivo.COMPLETO)
        self.assertEqual(nuevo.archivo_reemplazado, anterior)
        self.assertEqual(self.estudio.archivos.count(), 2)
        self.assertTrue(
            LogActividad.objects.filter(
                estudio=self.estudio,
                tipo_evento=TipoEvento.CORRECCION,
                resultado="Archivo reemplazado",
            ).exists()
        )
