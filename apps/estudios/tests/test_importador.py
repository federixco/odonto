"""Pruebas del análisis técnico de carpetas, sin tocar almacenamiento real."""

from io import BytesIO
from unittest.mock import patch

import pydicom
from django.test import TestCase
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from apps.archivos.models import Archivo
from apps.core.enums import CategoriaArchivo, EstadoArchivo, EstadoCuenta, EstadoImportacion, FormatoArchivo, RolUsuario
from apps.pacientes.models import Paciente
from apps.usuarios.models import Usuario
from apps.estudios.models import ImportacionEstudio
from apps.estudios.services.importador import analizar_importacion


def dicom_de_prueba():
    """Construye una cabecera DICOM mínima con datos ficticios de prueba."""

    meta = Dataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    dataset = FileDataset("prueba.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.PatientName = "GOMEZ^ANA"
    dataset.PatientID = "30111222"
    dataset.PatientBirthDate = "19900515"
    dataset.StudyDate = "20260910"
    dataset.StudyDescription = "Tomografía maxilar"
    dataset.StudyInstanceUID = generate_uid()
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False
    buffer = BytesIO()
    pydicom.dcmwrite(buffer, dataset)
    return buffer.getvalue()


class ImportadorTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin_detector",
            email="detector@example.com",
            password="clave-segura",
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente = Paciente.objects.create(
            nombre="Ana", apellido="Gómez", dni="30111222"
        )
        self.importacion = ImportacionEstudio.objects.create(
            iniciada_por=self.admin,
            nombre_carpeta="exportacion_prueba",
            cantidad_archivos=1,
            tamano_total=512,
        )
        Archivo.objects.create(
            importacion=self.importacion,
            nombre_archivo="001",
            ruta_relativa="DICOMRM/001",
            formato=FormatoArchivo.OTRO,
            categoria=CategoriaArchivo.PAQUETE_PROPIETARIO,
            ruta_almacenamiento="pruebas/001",
            tamano=512,
            estado=EstadoArchivo.COMPLETO,
        )

    @patch("apps.estudios.services.importador.leer_objeto")
    def test_dicom_sugiere_paciente_existente_sin_crear_otro(self, leer_objeto):
        leer_objeto.return_value = dicom_de_prueba()
        self.importacion.marcar_procesando()

        analizar_importacion(self.importacion)
        self.importacion.refresh_from_db()

        self.assertEqual(self.importacion.estado, EstadoImportacion.PENDIENTE_CONFIRMACION)
        self.assertEqual(self.importacion.paciente_sugerido, self.paciente)
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(self.importacion.datos_detectados["formato"], "DICOM")
        self.assertEqual(self.importacion.datos_detectados["nombre_paciente"], "GOMEZ ANA")
