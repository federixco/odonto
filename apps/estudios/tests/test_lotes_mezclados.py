"""Identidades incompatibles y fuentes clínicas al final de carpetas grandes."""

from io import BytesIO
from unittest.mock import patch

import pydicom
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from pydicom.dataset import Dataset

from apps.archivos.models import Archivo
from apps.core.enums import CategoriaArchivo, EstadoArchivo, FormatoArchivo
from apps.estudios.models import Estudio, ImportacionEstudio
from apps.estudios.services.identidad import IdentidadesLote
from apps.estudios.services.importador import _datos_desde_gwg16, analizar_importacion
from apps.estudios.tests.test_importador import dicom_de_prueba, dicomdir_de_prueba, gwg_de_prueba
from apps.pacientes.models import Paciente
from apps.usuarios.models import Usuario


def dicom_otro_paciente():
    dataset = pydicom.dcmread(BytesIO(dicom_de_prueba()))
    dataset.PatientID = "40111222"
    dataset.PatientName = "PEREZ^LUIS"
    buffer = BytesIO()
    pydicom.dcmwrite(buffer, dataset)
    return buffer.getvalue()


class IdentidadTests(SimpleTestCase):
    @patch("apps.estudios.services.importador._descomprimir_gwg16")
    def test_varios_patientinfo_en_un_gwg_no_se_ignoran(self, descomprimir):
        descomprimir.return_value = b'<DataContainerProperties><PatientInfo><ID>1</ID><FirstName>Ana</FirstName></PatientInfo><PatientInfo><ID>2</ID><FirstName>Luis</FirstName></PatientInfo></DataContainerProperties>'
        self.assertEqual(_datos_desde_gwg16(b"prueba")["_validacion_interna"]["estado"], "mezclado")

    def test_acentos_mayusculas_y_separadores_no_crean_conflicto(self):
        identidades = IdentidadesLote()
        identidades.agregar({"nombre_paciente": "GÓMEZ^ANA", "identificador_paciente": "30111222"})
        identidades.agregar({"nombre_paciente": "gomez ana", "identificador_paciente": "30111222"})
        self.assertEqual(identidades.resumen()["estado"], "consistente")

    def test_nombres_iguales_con_ids_distintos_son_incompatibles(self):
        identidades = IdentidadesLote()
        for identificador in ("30111222", "40111222"):
            identidades.agregar({"nombre_paciente": "GOMEZ ANA", "identificador_paciente": identificador})
        self.assertEqual(identidades.resumen()["estado"], "mezclado")
        self.assertNotIn("30111222", str(identidades.resumen()))

    def test_mismo_id_con_nacimiento_incompatible_se_bloquea(self):
        identidades = IdentidadesLote()
        for fecha in ("1990-05-15", "1991-05-15"):
            identidades.agregar({"identificador_paciente": "30111222", "fecha_nacimiento": fecha})
        self.assertEqual(identidades.resumen()["estado"], "mezclado")

    def test_sin_metadatos_no_se_declara_consistente(self):
        identidades = IdentidadesLote()
        identidades.agregar({})
        self.assertEqual(identidades.resumen()["estado"], "no_verificable")

    def test_nombre_sin_identificador_solo_da_verificacion_parcial(self):
        identidades = IdentidadesLote()
        identidades.agregar({"nombre_paciente": "GOMEZ ANA"})
        self.assertEqual(identidades.resumen()["estado"], "parcial")


class LotesMezcladosTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(username="admin_lotes", email="lotes@example.test", password="clave-test")
        self.paciente = Paciente.objects.create(nombre="Ana", apellido="Gomez", dni="30111222")
        self.lote = ImportacionEstudio.objects.create(iniciada_por=self.admin, nombre_carpeta="prueba")
        self.contenidos = {}
        self.client.force_login(self.admin)

    def agregar_archivo(self, nombre, contenido, formato=FormatoArchivo.DICOM):
        archivo = Archivo.objects.create(
            importacion=self.lote, nombre_archivo=nombre, ruta_relativa=f"carpeta/{nombre}",
            formato=formato, categoria=CategoriaArchivo.DICOM if formato == FormatoArchivo.DICOM else CategoriaArchivo.PAQUETE_PROPIETARIO,
            ruta_almacenamiento=f"pruebas/{nombre}", tamano=len(contenido), estado=EstadoArchivo.COMPLETO,
        )
        self.contenidos[archivo.ruta_almacenamiento] = contenido
        return archivo

    def analizar(self):
        self.lote.cantidad_archivos = self.lote.archivos.count()
        self.lote.tamano_total = sum(len(c) for c in self.contenidos.values())
        self.lote.save(update_fields=["cantidad_archivos", "tamano_total"])
        self.lote.marcar_procesando()
        with patch("apps.estudios.services.importador.leer_objeto", side_effect=lambda clave, limite: self.contenidos[clave][:limite]) as leer:
            analizar_importacion(self.lote)
        self.lote.refresh_from_db()
        return leer

    def test_detecta_otro_paciente_despues_de_los_primeros_25_archivos(self):
        for indice in range(30):
            self.agregar_archivo(f"{indice:03}.dcm", dicom_de_prueba())
        ultimo = self.agregar_archivo("999.dcm", dicom_otro_paciente())
        leer = self.analizar()
        self.assertTrue(self.lote.pacientes_mezclados)
        self.assertIsNone(self.lote.paciente_sugerido_id)
        self.assertNotIn("identificador_paciente", self.lote.datos_detectados)
        self.assertIn(ultimo.ruta_almacenamiento, {c.args[0] for c in leer.call_args_list})
        self.assertTrue(all(c.args[1] <= 256 * 1024 for c in leer.call_args_list))
        response = self.client.post(reverse("importacion_confirmar", args=[self.lote.pk]), {
            "paciente": self.paciente.pk, "tipo": "DICOM", "fecha_estudio": "2026-09-10",
        })
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Estudio.objects.exists())
        response = self.client.post(reverse("importacion_registrar_paciente", args=[self.lote.pk]), {
            "nombre": "Luis", "apellido": "Perez", "dni": "40111222",
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Paciente.objects.count(), 1)
        detalle = self.client.get(reverse("importacion_detalle", args=[self.lote.pk]))
        self.assertContains(detalle, "No podemos asociar esta carpeta")
        self.assertNotContains(detalle, 'action="' + reverse("importacion_confirmar", args=[self.lote.pk]) + '"')

    def test_dicomdir_con_varios_pacientes_no_elije_el_ultimo(self):
        dataset = pydicom.dcmread(BytesIO(dicomdir_de_prueba()))
        otro = Dataset()
        otro.DirectoryRecordType = "PATIENT"
        otro.PatientID = "40111222"
        otro.PatientName = "PEREZ^LUIS"
        dataset.DirectoryRecordSequence.append(otro)
        buffer = BytesIO()
        pydicom.dcmwrite(buffer, dataset)
        self.agregar_archivo("DICOMDIR", buffer.getvalue(), FormatoArchivo.OTRO)
        self.analizar()
        self.assertTrue(self.lote.pacientes_mezclados)
        self.assertNotIn("nombre_paciente", self.lote.datos_detectados)

    def test_galileos_y_dicom_de_pacientes_distintos_se_bloquean(self):
        self.agregar_archivo("a.gwg", gwg_de_prueba(), FormatoArchivo.GALILEOS)
        self.agregar_archivo("b.dcm", dicom_otro_paciente())
        self.analizar()
        self.assertTrue(self.lote.pacientes_mezclados)

    def test_un_solo_paciente_en_varias_instancias_se_permite(self):
        for indice in range(3):
            self.agregar_archivo(f"{indice}.dcm", dicom_de_prueba())
        self.analizar()
        self.assertFalse(self.lote.pacientes_mezclados)
        self.assertEqual(self.lote.paciente_sugerido_id, self.paciente.pk)
        self.assertEqual(self.lote.datos_detectados["validacion_pacientes"]["estado"], "consistente")

    def test_modelo_no_permite_confirmacion_directa_de_mezcla(self):
        self.agregar_archivo("a.dcm", dicom_de_prueba())
        self.agregar_archivo("b.dcm", dicom_otro_paciente())
        self.analizar()
        estudio = Estudio.objects.create(paciente=self.paciente, tipo="DICOM", fecha_estudio="2026-09-10")
        with self.assertRaises(ValidationError):
            self.lote.confirmar(estudio)
        self.assertIsNone(self.lote.archivos.get(nombre_archivo="a.dcm").estudio_id)
