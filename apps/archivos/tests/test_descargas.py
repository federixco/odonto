"""Pruebas de descarga segura y previsualización de archivos (Etapa 4)."""

import io
import zipfile
from datetime import date
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
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


class DescargasYPrevisualizacionTests(TransactionTestCase):
    # FileResponse.close() emite request_finished. Probamos ese cierre real sin
    # la transacción envolvente de TestCase, que inutiliza la conexión MySQL.
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

    @patch("apps.archivos.views.generar_url_descarga")
    def test_paciente_titular_no_puede_descargar_rf20(self, mock_generar):
        mock_generar.return_value = "http://s3.doc.local/presigned-paciente-download-url"
        self.client.login(username="paciente_doc", password=self.password)
        url = reverse("archivo_descargar", args=[self.archivo_dcm.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        mock_generar.assert_not_called()

        # Verificar auditoría
        log = LogActividad.objects.filter(
            estudio=self.estudio,
            usuario=self.user_paciente,
            tipo_evento=TipoEvento.DESCARGA,
        ).first()
        self.assertIsNone(log)

    def test_paciente_no_puede_descargar_estudio_ajeno(self):
        self.client.login(username="paciente_ajeno", password=self.password)
        url = reverse("archivo_descargar", args=[self.archivo_dcm.pk])
        resp = self.client.get(url)
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

    @patch("apps.estudios.views.get_s3_client")
    def test_descargar_estudio_completo_odontologo_autorizado(self, mock_s3_getter):
        mock_client = Mock()
        self.estudio.archivos.update(tamano=len(b"fake file content"))
        mock_client.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(b"fake file content")}
        mock_s3_getter.return_value = mock_client

        self.client.login(username="odon_doc", password=self.password)
        url = reverse("estudio_descargar_completo", args=[self.estudio.pk])
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/zip", resp.headers.get("Content-Type", ""))
        self.assertIn(f"Estudio_Garc", resp.headers.get("Content-Disposition", ""))
        self.assertIn(f"{self.estudio.pk}.zip", resp.headers.get("Content-Disposition", ""))
        with zipfile.ZipFile(io.BytesIO(b"".join(resp.streaming_content))) as paquete:
            self.assertEqual(set(paquete.namelist()), {"informe_clinico.pdf", "tomografia.dcm"})
            for nombre in paquete.namelist():
                self.assertEqual(paquete.read(nombre), b"fake file content")
        resp.close()

        # Verificar auditoría
        log = LogActividad.objects.filter(
            estudio=self.estudio,
            usuario=self.user_odon,
            tipo_evento=TipoEvento.DESCARGA,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("Descarga de carpeta raíz", log.detalles)

    @patch("apps.estudios.views.get_s3_client")
    def test_descargar_estudio_completo_paciente_bloqueado_rf20(self, mock_s3_getter):
        mock_client = Mock()
        self.estudio.archivos.update(tamano=len(b"fake file content"))
        mock_client.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(b"fake file content")}
        mock_s3_getter.return_value = mock_client

        self.client.login(username="paciente_doc", password=self.password)
        url = reverse("estudio_descargar_completo", args=[self.estudio.pk])
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 403)
        mock_s3_getter.assert_not_called()
        resp.close()

    def test_descargar_estudio_completo_paciente_ajeno_bloqueado(self):
        self.client.login(username="paciente_ajeno", password=self.password)
        url = reverse("estudio_descargar_completo", args=[self.estudio.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_descargar_estudio_completo_odontologo_no_autorizado_bloqueado(self):
        self.client.login(username="odon_ajeno", password=self.password)
        url = reverse("estudio_descargar_completo", args=[self.estudio.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    @patch("apps.archivos.views.generar_url_descarga")
    @patch("apps.archivos.views.generar_url_previsualizacion")
    def test_acceso_revocado_no_emite_nuevos_enlaces(self, preview, descarga):
        self.autorizacion.revocar(self.admin)
        self.client.force_login(self.user_odon)
        for ruta in ("archivo_descargar", "archivo_previsualizar"):
            response = self.client.get(reverse(ruta, args=[self.archivo_pdf.pk]))
            self.assertEqual(response.status_code, 403)
        preview.assert_not_called()
        descarga.assert_not_called()

    @patch("apps.archivos.views.generar_url_descarga")
    @patch("apps.archivos.views.generar_url_previsualizacion")
    def test_visitantes_y_usuarios_ajenos_no_emiten_enlaces(self, preview, descarga):
        for usuario in (None, self.user_odon_ajeno, self.user_paciente_ajeno):
            self.client.logout()
            if usuario:
                self.client.force_login(usuario)
            for ruta in ("archivo_descargar", "archivo_previsualizar"):
                response = self.client.get(reverse(ruta, args=[self.archivo_pdf.pk]))
                self.assertEqual(response.status_code, 403 if usuario else 302)
        preview.assert_not_called()
        descarga.assert_not_called()

    @patch("apps.archivos.views.generar_url_previsualizacion")
    @patch("apps.archivos.views.generar_url_descarga")
    def test_versiones_no_disponibles_no_generan_urls_para_ningun_rol(self, descarga, preview):
        for estado in (EstadoArchivo.CARGANDO, EstadoArchivo.INCORRECTO,
                       EstadoArchivo.REEMPLAZADO, EstadoArchivo.PURGADO):
            self.archivo_pdf.estado = estado
            self.archivo_pdf.save(update_fields=["estado"])
            for usuario in (self.admin, self.user_odon, self.user_paciente):
                self.client.force_login(usuario)
                for ruta in ("archivo_descargar", "archivo_previsualizar"):
                    with self.subTest(estado=estado, rol=usuario.rol, ruta=ruta):
                        response = self.client.get(reverse(ruta, args=[self.archivo_pdf.pk]))
                        self.assertEqual(response.status_code, 404)
        descarga.assert_not_called()
        preview.assert_not_called()
        self.assertFalse(LogActividad.objects.exists())

    @patch("apps.estudios.views.get_s3_client")
    def test_zip_entrega_el_reemplazo_y_conserva_la_estructura(self, obtener_s3):
        self.archivo_pdf.estado = EstadoArchivo.REEMPLAZADO
        self.archivo_pdf.save(update_fields=["estado"])
        nuevo = Archivo.objects.create(
            estudio=self.estudio, nombre_archivo="informe_clinico.pdf",
            ruta_relativa="informes/informe_clinico.pdf", formato=FormatoArchivo.PDF,
            categoria=CategoriaArchivo.IMAGEN_DOCUMENTO,
            ruta_almacenamiento="estudios/1/informe-corregido.pdf", tamano=9,
            estado=EstadoArchivo.COMPLETO, archivo_reemplazado=self.archivo_pdf,
        )
        self.archivo_dcm.tamano = 5
        self.archivo_dcm.save(update_fields=["tamano"])
        cuerpos = {nuevo.ruta_almacenamiento: b"corregido",
                   self.archivo_dcm.ruta_almacenamiento: b"DICOM"}
        s3 = obtener_s3.return_value
        s3.get_object.side_effect = lambda **kw: {"Body": io.BytesIO(cuerpos[kw["Key"]])}
        self.client.force_login(self.user_odon)
        response = self.client.get(reverse("estudio_descargar_completo", args=[self.estudio.pk]))
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content))) as paquete:
            self.assertEqual(set(paquete.namelist()), {"informes/informe_clinico.pdf", "tomografia.dcm"})
            self.assertEqual(paquete.read("informes/informe_clinico.pdf"), b"corregido")
            self.assertEqual(paquete.read("tomografia.dcm"), b"DICOM")
        response.close()

    @patch("apps.estudios.views.get_s3_client")
    def test_zip_no_devuelve_paquete_parcial_si_falla_un_objeto(self, obtener_s3):
        cuerpo = io.BytesIO(b"PDF")
        self.archivo_pdf.tamano = 3
        self.archivo_pdf.save(update_fields=["tamano"])
        obtener_s3.return_value.get_object.side_effect = [
            {"Body": cuerpo}, RuntimeError("Objeto faltante simulado"),
        ]
        self.client.force_login(self.user_odon)
        with self.assertLogs("apps.estudios.views", level="ERROR"):
            response = self.client.get(reverse("estudio_descargar_completo", args=[self.estudio.pk]))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertTrue(cuerpo.closed)
        self.assertEqual(LogActividad.objects.get().resultado, "Error al preparar paquete ZIP")

    @patch("apps.estudios.views.get_s3_client")
    def test_zip_rechaza_objeto_truncado(self, obtener_s3):
        cuerpo = io.BytesIO(b"contenido demasiado corto")
        obtener_s3.return_value.get_object.return_value = {"Body": cuerpo}
        self.client.force_login(self.user_odon)
        with self.assertLogs("apps.estudios.views", level="ERROR"):
            response = self.client.get(reverse("estudio_descargar_completo", args=[self.estudio.pk]))
        self.assertEqual(response.status_code, 502)
        self.assertTrue(cuerpo.closed)
        self.assertFalse(LogActividad.objects.filter(resultado="Paquete ZIP preparado").exists())

    @patch("apps.estudios.views.get_s3_client")
    def test_zip_lee_por_bloques_y_cierra_cuerpos_y_temporal(self, obtener_s3):
        import tempfile

        from apps.estudios.views import ZIP_CHUNK_SIZE

        class CuerpoAcotado(io.BytesIO):
            def read(self, cantidad=-1):
                if cantidad <= 0 or cantidad > ZIP_CHUNK_SIZE:
                    raise AssertionError("Lectura de archivo sin límite de memoria")
                return super().read(cantidad)

        contenido = b"x" * (ZIP_CHUNK_SIZE * 2 + 37)
        self.estudio.archivos.update(tamano=len(contenido))
        cuerpos = []

        def obtener_objeto(**kwargs):
            cuerpo = CuerpoAcotado(contenido)
            cuerpos.append(cuerpo)
            return {"Body": cuerpo}

        obtener_s3.return_value.get_object.side_effect = obtener_objeto
        self.client.force_login(self.admin)
        temporal = tempfile.TemporaryFile()
        with patch("apps.estudios.views.tempfile.TemporaryFile", return_value=temporal):
            response = self.client.get(reverse("estudio_descargar_completo", args=[self.estudio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(cuerpo.closed for cuerpo in cuerpos))
        obtener_s3.return_value.close.assert_called_once()
        with zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content))) as paquete:
            for nombre in paquete.namelist():
                self.assertEqual(paquete.read(nombre), contenido)
        response.close()
        self.assertTrue(temporal.closed)

    @override_settings(ZIP_MAX_TAMANO_TOTAL=1)
    @patch("apps.estudios.views.get_s3_client")
    def test_zip_limite_de_tamano_no_inicia_lecturas(self, obtener_s3):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("estudio_descargar_completo", args=[self.estudio.pk]))
        self.assertEqual(response.status_code, 413)
        obtener_s3.assert_not_called()

    @override_settings(ZIP_MAX_ARCHIVOS=1)
    @patch("apps.estudios.views.get_s3_client")
    def test_zip_limite_de_entradas_acota_metadatos_en_ram(self, obtener_s3):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("estudio_descargar_completo", args=[self.estudio.pk]))
        self.assertEqual(response.status_code, 413)
        obtener_s3.assert_not_called()

    @patch("apps.estudios.views.shutil.disk_usage")
    @patch("apps.estudios.views.get_s3_client")
    def test_zip_sin_espacio_no_inicia_lecturas(self, obtener_s3, espacio):
        espacio.return_value.free = 0
        self.client.force_login(self.admin)
        response = self.client.get(reverse("estudio_descargar_completo", args=[self.estudio.pk]))
        self.assertEqual(response.status_code, 507)
        obtener_s3.assert_not_called()

    @patch("apps.core.concurrencia.bloquear_recurso")
    @patch("apps.estudios.views.get_s3_client")
    def test_zip_otro_armado_en_curso_no_acumula_trabajos(self, obtener_s3, bloqueo):
        from apps.core.concurrencia import RecursoOcupado

        bloqueo.return_value.__enter__.side_effect = RecursoOcupado()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("estudio_descargar_completo", args=[self.estudio.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response["Retry-After"], "2")
        obtener_s3.assert_not_called()

    @patch("apps.estudios.views.get_s3_client")
    def test_zip_cierra_cuerpo_y_temporal_si_falla_la_lectura(self, obtener_s3):
        import tempfile

        class CuerpoInterrumpido(io.BytesIO):
            def read(self, cantidad=-1):
                raise OSError("Corte de transferencia simulado")

        cuerpo = CuerpoInterrumpido(b"PDF")
        obtener_s3.return_value.get_object.return_value = {"Body": cuerpo}
        temporal = tempfile.TemporaryFile()
        self.client.force_login(self.admin)
        with patch("apps.estudios.views.tempfile.TemporaryFile", return_value=temporal):
            with self.assertLogs("apps.estudios.views", level="ERROR"):
                response = self.client.get(reverse("estudio_descargar_completo", args=[self.estudio.pk]))
        self.assertEqual(response.status_code, 502)
        self.assertTrue(cuerpo.closed)
        self.assertTrue(temporal.closed)

