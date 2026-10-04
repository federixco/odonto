"""Pruebas del análisis técnico de carpetas, sin tocar almacenamiento real."""

import gzip
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


def gwg_de_prueba():
    """Construye un GWG16 mínimo sin depender de archivos clínicos reales."""

    xml = b"""<?xml version="1.0" encoding="utf-16"?>
<DataContainerProperties>
  <TimeStamp>202609121430</TimeStamp>
  <Version>1.9</Version>
  <SoftwareVersion>Galileos Implant 1.9.test</SoftwareVersion>
  <ScanID>scan-de-prueba</ScanID>
  <Format>Encrypted</Format>
  <PatientInfo>
    <FirstName>ANA</FirstName>
    <LastName>GOMEZ</LastName>
    <BirthDate>19900515</BirthDate>
    <ID>30111222</ID>
  </PatientInfo>
  <DataSource>WrapAndGo17</DataSource>
</DataContainerProperties>"""
    clave = bytes.fromhex("cd1f220e1cbea66a82eeaf5b")
    cifrado = bytearray(gzip.compress(xml, mtime=0))
    palabras = len(cifrado) // 4
    for indice in range(palabras):
        inicio = indice * 4
        inicio_clave = (indice % (len(clave) // 4)) * 4
        for desplazamiento in range(4):
            cifrado[inicio + desplazamiento] ^= clave[inicio_clave + desplazamiento]
    for indice in range(palabras * 4, len(cifrado)):
        cifrado[indice] ^= clave[indice - palabras * 4]
    return b"GWG16" + bytes(cifrado)


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


def dicomdir_de_prueba():
    """Construye un DICOMDIR con los datos dentro de registros anidados."""

    meta = Dataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    dataset = FileDataset("DICOMDIR", {}, file_meta=meta, preamble=b"\0" * 128)
    paciente = Dataset()
    paciente.DirectoryRecordType = "PATIENT"
    paciente.PatientName = "TOMAS^SANDRA PATRICIA^^^"
    paciente.PatientID = "20877656"
    estudio = Dataset()
    estudio.DirectoryRecordType = "STUDY"
    estudio.StudyDate = "20260818"
    estudio.StudyDescription = "Exploracion 3D"
    estudio.StudyInstanceUID = generate_uid()
    dataset.DirectoryRecordSequence = [paciente, estudio]
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

    @patch("apps.estudios.services.importador.leer_objeto")
    def test_dicomdir_lee_paciente_y_estudio_de_registros_anidados(self, leer_objeto):
        leer_objeto.return_value = dicomdir_de_prueba()
        archivo = self.importacion.archivos.get()
        archivo.ruta_relativa = "paquete/DICOMDIR"
        archivo.save(update_fields=["ruta_relativa", "updated_at"])
        self.importacion.marcar_procesando()

        analizar_importacion(self.importacion)
        self.importacion.refresh_from_db()

        datos = self.importacion.datos_detectados
        self.assertEqual(datos["nombre_paciente"], "TOMAS SANDRA PATRICIA")
        self.assertEqual(datos["identificador_paciente"], "20877656")
        self.assertEqual(datos["fecha_estudio"], "2026-08-18")
        self.assertEqual(datos["descripcion"], "Exploracion 3D")

    @patch("apps.estudios.services.importador.leer_objeto")
    def test_carpeta_dicom_mixta_conserva_formatos_individuales(self, leer_objeto):
        contenidos = {"pruebas/001": dicom_de_prueba()}
        formatos = [
            ("informe.pdf", FormatoArchivo.PDF, CategoriaArchivo.IMAGEN_DOCUMENTO, b"%PDF-1.7"),
            ("imagen.jpg", FormatoArchivo.JPG, CategoriaArchivo.IMAGEN_DOCUMENTO, b"\xff\xd8\xff"),
            ("modelo.stl", FormatoArchivo.STL, CategoriaArchivo.MODELO_3D, b"solid modelo"),
            ("instalador.exe", FormatoArchivo.OTRO, CategoriaArchivo.PAQUETE_PROPIETARIO, b"MZauxiliar"),
            ("002", FormatoArchivo.OTRO, CategoriaArchivo.PAQUETE_PROPIETARIO, dicom_de_prueba()),
        ]
        originales = []
        for nombre, formato, categoria, contenido in formatos:
            clave = f"pruebas/{nombre}"
            contenidos[clave] = contenido
            archivo = Archivo.objects.create(
                importacion=self.importacion, nombre_archivo=nombre,
                ruta_relativa=f"carpeta/{nombre}", formato=formato, categoria=categoria,
                ruta_almacenamiento=clave, tamano=10, estado=EstadoArchivo.COMPLETO,
            )
            originales.append((archivo, formato, categoria))
        self.importacion.cantidad_archivos = 6
        self.importacion.tamano_total = 562
        self.importacion.save(update_fields=["cantidad_archivos", "tamano_total"])
        leer_objeto.side_effect = lambda clave, limite: contenidos[clave][:limite]
        self.importacion.marcar_procesando()

        analizar_importacion(self.importacion)

        self.importacion.refresh_from_db()
        self.assertEqual(self.importacion.datos_detectados["formato"], "DICOM")
        self.assertEqual(self.importacion.paciente_sugerido_id, self.paciente.pk)
        for archivo, formato, categoria in originales:
            archivo.refresh_from_db()
            if archivo.nombre_archivo == "002":
                self.assertEqual(archivo.formato, FormatoArchivo.DICOM)
                self.assertEqual(archivo.categoria, CategoriaArchivo.DICOM)
            else:
                self.assertEqual(archivo.formato, formato)
                self.assertEqual(archivo.categoria, categoria)
        original = self.importacion.archivos.get(nombre_archivo="001")
        self.assertEqual(original.formato, FormatoArchivo.DICOM)
        # No leer PDF/JPG/STL para reclasificar el lote entero.
        claves_leidas = {llamada.args[0] for llamada in leer_objeto.call_args_list}
        self.assertFalse({"pruebas/informe.pdf", "pruebas/imagen.jpg", "pruebas/modelo.stl"} & claves_leidas)
        lecturas_auxiliares = [
            llamada.args[1] for llamada in leer_objeto.call_args_list
            if llamada.args[0] in {"pruebas/002", "pruebas/instalador.exe"}
        ]
        self.assertEqual(lecturas_auxiliares, [132, 132, 256 * 1024])

    @patch("apps.estudios.services.importador.leer_objeto")
    def test_gwg16_extrae_datos_y_sugiere_paciente_por_dni(self, leer_objeto):
        leer_objeto.return_value = gwg_de_prueba()
        archivo = self.importacion.archivos.get()
        archivo.nombre_archivo = "scan-de-prueba.gwg"
        archivo.ruta_relativa = "GOMEZ ANA GAL/scan-de-prueba.gwg"
        archivo.save(update_fields=["nombre_archivo", "ruta_relativa", "updated_at"])
        self.importacion.nombre_carpeta = "GOMEZ ANA GAL"
        self.importacion.save(update_fields=["nombre_carpeta", "updated_at"])
        self.importacion.marcar_procesando()

        analizar_importacion(self.importacion)
        self.importacion.refresh_from_db()

        datos = self.importacion.datos_detectados
        self.assertEqual(datos["formato"], "GALILEOS")
        self.assertEqual(datos["nombre_paciente"], "GOMEZ ANA")
        self.assertEqual(datos["identificador_paciente"], "30111222")
        self.assertEqual(datos["fecha_nacimiento"], "1990-05-15")
        self.assertEqual(datos["fecha_estudio"], "2026-09-12")
        self.assertEqual(datos["scan_id"], "scan-de-prueba")
        self.assertEqual(datos["data_source"], "WrapAndGo17")
        self.assertEqual(datos["parser"], "galileos-gwg16-v1")
        self.assertEqual(self.importacion.paciente_sugerido, self.paciente)

    @patch("apps.estudios.services.importador.leer_objeto")
    def test_gwg_desconocido_conserva_deteccion_por_nombre_carpeta(self, leer_objeto):
        leer_objeto.return_value = b"GWG99contenido-no-compatible"
        archivo = self.importacion.archivos.get()
        archivo.nombre_archivo = "estudio.gwg"
        archivo.ruta_relativa = "tOMAS sANDRA gAL/estudio.gwg"
        archivo.save(update_fields=["nombre_archivo", "ruta_relativa", "updated_at"])
        self.importacion.nombre_carpeta = "tOMAS sANDRA gAL"
        self.importacion.save(update_fields=["nombre_carpeta", "updated_at"])
        self.importacion.marcar_procesando()

        analizar_importacion(self.importacion)
        self.importacion.refresh_from_db()

        datos = self.importacion.datos_detectados
        self.assertEqual(datos["formato"], "GALILEOS")
        self.assertEqual(datos["nombre_paciente"], "Tomas Sandra")
        self.assertNotIn("identificador_paciente", datos)
        self.assertIn("nombre de la carpeta", datos["advertencias"][0])
        self.assertIsNone(self.importacion.paciente_sugerido)
