"""Regresiones de cargas/cola. Ejecutar con config.settings.test_mysql, no S3 real."""
from datetime import timedelta
from threading import Event, Thread
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.archivos.models import Archivo
from apps.core.concurrencia import bloquear_recurso, RecursoOcupado
from apps.core.enums import EstadoArchivo, EstadoCuenta, EstadoImportacion, FormatoArchivo, CategoriaArchivo, RolUsuario
from apps.estudios.models import ImportacionEstudio
from apps.estudios.services.cancelacion import limpiar_cancelada
from apps.estudios.services.trabajos import encolar, reservar, ControlAnalisis, AnalisisInterrumpido, procesar_uno
from apps.pacientes.models import Paciente
from apps.usuarios.models import Usuario, Odontologo


class CargasAsincronasTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(username="admin_async", email="async@example.test", password="clave-test")
        self.client.force_login(self.admin)
        self.lote = ImportacionEstudio.objects.create(iniciada_por=self.admin, nombre_carpeta="carpeta", cantidad_archivos=1, tamano_total=10)
        self.archivo = Archivo.objects.create(importacion=self.lote, nombre_archivo="001.dcm", ruta_relativa="carpeta/001.dcm",
            formato=FormatoArchivo.DICOM, categoria=CategoriaArchivo.DICOM, ruta_almacenamiento="pruebas/001",
            tamano=10, estado=EstadoArchivo.COMPLETO)

    def post(self, nombre, data=None, archivo=False):
        args = [self.lote.pk, self.archivo.pk] if archivo else [self.lote.pk]
        return self.client.post(reverse(nombre, args=args), data or {}, content_type="application/json")

    @patch("apps.estudios.services.importador.analizar_importacion")
    def test_http_encola_sin_leer_archivos(self, analizar):
        response = self.post("importacion_analizar")
        self.assertEqual(response.status_code, 202)
        analizar.assert_not_called()
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.estado, EstadoImportacion.PROCESANDO)
        self.assertEqual(self.lote.datos_detectados["_analisis"]["estado"], "pendiente")

    def test_doble_post_no_reinicia_reserva(self):
        self.post("importacion_analizar")
        _, token = reservar()
        self.assertEqual(self.post("importacion_analizar").status_code, 202)
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.datos_detectados["_analisis"]["token"], token)
        self.assertIsNone(reservar())

    def test_no_encola_lote_incompleto(self):
        self.archivo.estado = EstadoArchivo.CARGANDO
        self.archivo.save(update_fields=["estado"])
        self.assertEqual(self.post("importacion_analizar").status_code, 409)

    def test_reserva_vencida_invalida_worker_anterior(self):
        encolar(self.lote)
        _, anterior = reservar()
        self.lote.refresh_from_db()
        self.lote.datos_detectados["_analisis"]["vence"] = (timezone.now() - timedelta(seconds=1)).isoformat()
        self.lote.save(update_fields=["datos_detectados"])
        _, nuevo = reservar()
        self.assertNotEqual(anterior, nuevo)
        with self.assertRaises(AnalisisInterrumpido):
            ControlAnalisis(self.lote.pk, anterior)(forzar=True)

    def test_cancelar_impide_resultado_tardio(self):
        encolar(self.lote)
        _, token = reservar()
        self.assertEqual(self.post("importacion_cancelar").status_code, 202)
        with self.assertRaises(AnalisisInterrumpido):
            ControlAnalisis(self.lote.pk, token)(forzar=True)
        self.lote.marcar_error("No debe reabrir el lote")
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.estado, EstadoImportacion.CANCELADA)

    @patch("apps.estudios.services.cancelacion.eliminar_objeto")
    @patch("apps.estudios.services.cancelacion.abortar_multipart_upload", return_value=False)
    def test_cancelacion_reintentable_conserva_id_si_s3_no_confirma(self, abortar, eliminar):
        self.archivo.estado, self.archivo.upload_id = EstadoArchivo.CARGANDO, "pendiente"
        self.archivo.save(update_fields=["estado", "upload_id"])
        self.lote.cancelar()
        self.assertEqual(limpiar_cancelada(self.lote), 1)
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.upload_id, "pendiente")
        eliminar.assert_not_called()

    @patch("apps.estudios.services.cancelacion.eliminar_objeto", return_value=True)
    def test_limpieza_cancelada_es_idempotente(self, eliminar):
        self.lote.cancelar()
        self.assertEqual(limpiar_cancelada(self.lote), 0)
        self.assertEqual(limpiar_cancelada(self.lote), 0)
        self.archivo.refresh_from_db()
        self.assertEqual(self.archivo.estado, EstadoArchivo.PURGADO)
        eliminar.assert_called_once()

    def test_solicitud_inicio_repetida_no_duplica_lote(self):
        data = {"nombre_carpeta": "otra", "cantidad_archivos": 1, "tamano_total": 10, "solicitud_id": str(uuid4())}
        uno = self.client.post(reverse("importacion_iniciar"), data, content_type="application/json")
        dos = self.client.post(reverse("importacion_iniciar"), data, content_type="application/json")
        self.assertEqual(uno.json()["importacion_id"], dos.json()["importacion_id"])

    @patch("apps.estudios.views.iniciar_multipart_upload")
    def test_reintentar_archivo_completo_no_inicia_otro_multipart(self, iniciar):
        response = self.post("importacion_archivo_iniciar", {"ruta_relativa": self.archivo.ruta_relativa, "tamano": 10})
        self.assertEqual(response.json()["status"], "completo")
        iniciar.assert_not_called()
        self.assertEqual(self.lote.archivos.count(), 1)

    @patch("apps.estudios.views.completar_multipart_upload")
    def test_completar_dos_veces_es_idempotente(self, completar):
        response = self.post("importacion_archivo_completar", archivo=True)
        self.assertEqual(response.status_code, 200)
        completar.assert_not_called()

    @patch("apps.estudios.views.completar_multipart_upload")
    def test_generacion_anterior_no_completa_nueva_carga(self, completar):
        self.archivo.estado, self.archivo.upload_id = EstadoArchivo.CARGANDO, "nuevo"
        self.archivo.save(update_fields=["estado", "upload_id"])
        response = self.post("importacion_archivo_completar", {"partes": [{"PartNumber":1,"ETag":"etag"}], "carga_token":"viejo"}, archivo=True)
        self.assertEqual(response.status_code, 409)
        completar.assert_not_called()

    @patch("apps.estudios.services.trabajos.calcular_sha256_objeto", return_value="a" * 64)
    @patch("apps.estudios.services.importador._inspeccionar_lote", return_value={"formato":"DICOM"})
    def test_worker_finaliza_hash_y_analisis(self, inspeccionar, sha):
        encolar(self.lote)
        self.assertTrue(procesar_uno())
        self.lote.refresh_from_db(); self.archivo.refresh_from_db()
        self.assertEqual(self.lote.estado, EstadoImportacion.PENDIENTE_CONFIRMACION)
        self.assertEqual(self.archivo.hash_sha256, "a" * 64)
        self.assertEqual(self.lote.datos_detectados["_analisis"]["estado"], "completo")

    @patch("apps.estudios.services.trabajos.calcular_sha256_objeto", side_effect=RuntimeError("simulado"))
    def test_worker_aplica_backoff_sin_bucle_inmediato(self, sha):
        encolar(self.lote)
        with self.assertLogs("apps.estudios.services.trabajos", level="ERROR"):
            procesar_uno()
        self.assertIsNone(reservar())
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.datos_detectados["_analisis"]["estado"], "pendiente")

    def test_estado_de_otro_admin_no_es_visible(self):
        otro = Usuario.objects.create_superuser(username="otro_async", email="otro@example.test", password="test")
        self.client.force_login(otro)
        self.assertEqual(self.client.get(reverse("importacion_estado", args=[self.lote.pk])).status_code, 404)

    def test_estado_no_expone_token_ni_datos_clinicos(self):
        encolar(self.lote); reservar()
        response = self.client.get(reverse("importacion_estado", args=[self.lote.pk]))
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotContains(response, "token")
        self.assertNotContains(response, "nombre_paciente")

    def test_cancelacion_solo_admite_post(self):
        self.assertEqual(self.client.get(reverse("importacion_cancelar", args=[self.lote.pk])).status_code, 405)


class SelectoresRemotosTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(username="admin_selector", email="selector@example.test", password="test")
        self.client.force_login(self.admin)
        Paciente.objects.bulk_create([Paciente(nombre="Paciente", apellido=f"Apellido{i:02}", dni=str(71000000+i)) for i in range(47)])

    def test_pagina_acotada_y_orden_estable(self):
        uno = self.client.get(reverse("selector_pacientes")).json()
        dos = self.client.get(reverse("selector_pacientes"), {"page":2}).json()
        self.assertEqual(len(uno["resultados"]), 20)
        self.assertEqual(uno["total"], 47)
        self.assertFalse({x["id"] for x in uno["resultados"]} & {x["id"] for x in dos["resultados"]})

    def test_dni_exacto_fuera_de_primera_pagina(self):
        data = self.client.get(reverse("selector_pacientes"), {"dni":"71000046"}).json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["resultados"][0]["dni"], "71000046")

    def test_seleccion_se_conserva_fuera_del_filtro(self):
        paciente = Paciente.objects.order_by("pk").last()
        data = self.client.get(reverse("selector_pacientes"), {"q":"noexiste", "seleccionado":paciente.pk}).json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["seleccionado"]["id"], paciente.pk)

    def test_no_entrega_datos_a_anonimos(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("selector_pacientes")).status_code, 302)

    def test_odontologos_inhabilitados_no_se_ofrecen(self):
        for i, estado in enumerate((EstadoCuenta.HABILITADA, EstadoCuenta.PENDIENTE)):
            usuario = Usuario.objects.create_user(username=f"odontologo_sel{i}", email=f"odonto{i}@example.test", password="test", rol=RolUsuario.ODONTOLOGO, estado=estado)
            Odontologo.objects.create(usuario=usuario, nombre="Profesional", apellido="Prueba", matricula=f"mat{i}")
        data = self.client.get(reverse("selector_odontologos")).json()
        self.assertEqual(data["total"], 1)


class ExclusividadMySQLTests(TransactionTestCase):
    def preparar_lote(self):
        self.admin = Usuario.objects.create_superuser(username="admin_paralelo", email="paralelo@example.test", password="test")
        self.client.force_login(self.admin)
        self.lote = ImportacionEstudio.objects.create(iniciada_por=self.admin, nombre_carpeta="carpeta", cantidad_archivos=1, tamano_total=10)
        self.archivo = Archivo.objects.create(importacion=self.lote, nombre_archivo="001.dcm", ruta_relativa="carpeta/001.dcm",
            formato=FormatoArchivo.DICOM, categoria=CategoriaArchivo.DICOM, ruta_almacenamiento="pruebas/paralelo",
            tamano=10, estado=EstadoArchivo.CARGANDO, upload_id="multipart-paralelo")

    def transferencia_paralela(self, cancelar=False):
        if connection.vendor != "mysql":
            self.skipTest("Requiere MySQL; no sustituir por SQLite.")
        self.preparar_lote()
        inicio, continuar = Event(), Event()
        respuestas, errores = [], []
        url = reverse("importacion_archivo_completar", args=[self.lote.pk, self.archivo.pk])
        datos = {"partes":[{"PartNumber":1,"ETag":"etag"}], "carga_token":"multipart-paralelo"}
        def s3(*args):
            inicio.set()
            if not continuar.wait(10):
                raise RuntimeError("La prueba no liberó la transferencia.")
            return {"tamano":10}
        def completar():
            try:
                close_old_connections()
                cliente = Client(); cliente.force_login(self.admin)
                respuestas.append(cliente.post(url, datos, content_type="application/json").status_code)
            except Exception as error:
                errores.append(error); inicio.set()
            finally:
                connections["default"].close()
        with patch("apps.estudios.views.completar_multipart_upload", side_effect=s3) as remoto, patch("apps.estudios.views.eliminar_objeto", return_value=True):
            hilo = Thread(target=completar); hilo.start()
            try:
                self.assertTrue(inicio.wait(5)); self.assertFalse(errores)
                if cancelar:
                    response = self.client.post(reverse("importacion_cancelar", args=[self.lote.pk]))
                    self.assertEqual(response.status_code, 202)
                else:
                    response = self.client.post(url, datos, content_type="application/json")
                    self.assertEqual(response.status_code, 409)
                    self.assertTrue(response.json()["reintentable"])
            finally:
                continuar.set(); hilo.join(10)
            self.assertFalse(hilo.is_alive()); self.assertFalse(errores)
            remoto.assert_called_once()
        self.lote.refresh_from_db(); self.archivo.refresh_from_db()
        if cancelar:
            self.assertEqual(self.lote.estado, EstadoImportacion.CANCELADA)
            self.assertNotEqual(self.archivo.estado, EstadoArchivo.COMPLETO)
        else:
            self.assertEqual(respuestas, [200])
            self.assertEqual(self.archivo.estado, EstadoArchivo.COMPLETO)

    def test_dos_completados_no_ensamblan_el_objeto_dos_veces(self):
        self.transferencia_paralela()

    def test_cancelar_durante_verificacion_no_reabre_lote(self):
        self.transferencia_paralela(cancelar=True)

    def test_dos_conexiones_no_pueden_operar_el_mismo_archivo(self):
        if connection.vendor != "mysql":
            self.skipTest("Requiere MySQL; no sustituir por SQLite.")
        listo, soltar = Event(), Event()
        errores = []
        def retener():
            try:
                close_old_connections()
                with bloquear_recurso("test:archivo-concurrente"):
                    listo.set()
                    soltar.wait(10)
            except Exception as error:
                errores.append(error); listo.set()
            finally:
                connections["default"].close()
        hilo = Thread(target=retener)
        hilo.start()
        try:
            self.assertTrue(listo.wait(5))
            self.assertFalse(errores)
            with self.assertRaises(RecursoOcupado):
                with bloquear_recurso("test:archivo-concurrente"):
                    self.fail("El segundo proceso obtuvo un recurso ocupado.")
        finally:
            soltar.set(); hilo.join(5)
        self.assertFalse(hilo.is_alive())
