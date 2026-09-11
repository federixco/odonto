"""Pruebas de publicación y eliminación lógica de estudios."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.accesos.models import Autorizacion
from apps.archivos.models import Archivo
from apps.core.enums import (
    CategoriaArchivo,
    EstadoArchivo,
    EstadoCuenta,
    EstadoEstudio,
    EstadoImportacion,
    FormatoArchivo,
    RolUsuario,
)
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo, Usuario

from apps.estudios.models import Estudio, ImportacionEstudio


class EstudioModelTests(TestCase):
    def setUp(self):
        paciente = Paciente.objects.create(
            nombre="Juan",
            apellido="Gómez",
            dni="12345678",
        )
        self.estudio = Estudio.objects.create(
            paciente=paciente,
            tipo="Tomografía",
            fecha_estudio="2026-08-30",
        )

        cuenta_odontologo = Usuario.objects.create_user(
            username="derivante",
            email="derivante@example.com",
            password="clave-segura",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        odontologo = Odontologo.objects.create(
            usuario=cuenta_odontologo,
            nombre="Ana",
            apellido="Pérez",
            matricula="MAT-001",
        )
        Autorizacion.objects.create(
            odontologo=odontologo,
            estudio=self.estudio,
        )

    def crear_archivo(self, estado):
        return Archivo.objects.create(
            estudio=self.estudio,
            nombre_archivo="estudio.dcm",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="estudios/estudio.dcm",
            tamano=1024,
            hash_sha256="a" * 64,
            estado=estado,
        )

    def test_no_publica_archivos_incompletos(self):
        self.crear_archivo(EstadoArchivo.CARGANDO)

        self.assertFalse(self.estudio.validar_carga())
        with self.assertRaises(ValidationError):
            self.estudio.publicar()

    def test_publica_estudio_completo_y_autorizado(self):
        self.crear_archivo(EstadoArchivo.COMPLETO)

        self.assertTrue(self.estudio.validar_carga())
        self.estudio.publicar()
        self.estudio.refresh_from_db()

        self.assertEqual(self.estudio.estado, EstadoEstudio.PUBLICADO)
        self.assertIsNotNone(self.estudio.fecha_publicacion)

    def test_delete_realiza_eliminacion_logica(self):
        estudio_id = self.estudio.pk

        self.estudio.delete()

        estudio = Estudio.objects.get(pk=estudio_id)
        self.assertEqual(estudio.estado, EstadoEstudio.ELIMINADO)


class ImportacionEstudioModelTests(TestCase):
    """Pruebas de las reglas persistentes del lote de importación."""

    def setUp(self):
        self.administrador = Usuario.objects.create_superuser(
            username="admin_importaciones",
            email="admin.importaciones@example.com",
            password="clave-segura",
        )
        self.paciente = Paciente.objects.create(
            nombre="Paciente",
            apellido="Prueba",
            dni="87654321",
        )
        self.estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía",
            fecha_estudio="2026-09-10",
        )
        self.importacion = ImportacionEstudio.objects.create(
            iniciada_por=self.administrador,
            paciente_sugerido=self.paciente,
            nombre_carpeta="exportacion_estudio",
            cantidad_archivos=1,
            tamano_total=1024,
            datos_detectados={"formato": "DICOM"},
        )

    def crear_archivo(self, estado=EstadoArchivo.COMPLETO, **datos):
        valores = {
            "importacion": self.importacion,
            "nombre_archivo": "001",
            "ruta_relativa": "DICOMRM/CT3/001",
            "formato": FormatoArchivo.DICOM,
            "categoria": CategoriaArchivo.DICOM,
            "ruta_almacenamiento": "importaciones/1/DICOMRM/CT3/001",
            "tamano": 1024,
            "hash_sha256": "b" * 64,
            "estado": estado,
        }
        valores.update(datos)
        return Archivo.objects.create(**valores)

    def test_importacion_puede_existir_antes_del_estudio_confirmado(self):
        self.assertIsNone(self.importacion.estudio)
        self.assertEqual(self.importacion.estado, EstadoImportacion.CARGANDO)

    def test_procesa_y_confirma_una_importacion_completa(self):
        self.crear_archivo()

        self.importacion.marcar_procesando()
        self.importacion.marcar_pendiente_confirmacion()
        resultado = self.importacion.confirmar(self.estudio)
        self.importacion.refresh_from_db()

        self.assertEqual(resultado, self.estudio)
        self.assertEqual(self.importacion.estudio, self.estudio)
        self.assertEqual(self.importacion.estado, EstadoImportacion.CONFIRMADA)
        self.assertEqual(resultado.archivos.count(), 1)

    def test_no_procesa_importacion_con_archivos_incompletos(self):
        self.crear_archivo(estado=EstadoArchivo.CARGANDO)

        with self.assertRaises(ValidationError):
            self.importacion.marcar_procesando()

    def test_no_procesa_si_faltan_archivos_de_la_carpeta(self):
        self.importacion.cantidad_archivos = 2
        self.importacion.save(update_fields=["cantidad_archivos", "updated_at"])
        self.crear_archivo()

        self.assertFalse(self.importacion.esta_completa())
        with self.assertRaises(ValidationError):
            self.importacion.marcar_procesando()

    def test_solo_administrador_puede_iniciar_importacion(self):
        odontologo = Usuario.objects.create_user(
            username="odontologo_importacion",
            email="odontologo.importacion@example.com",
            password="clave-segura",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        importacion = ImportacionEstudio(
            iniciada_por=odontologo,
            nombre_carpeta="carpeta_no_permitida",
        )

        with self.assertRaises(ValidationError):
            importacion.full_clean()

    def test_archivo_rechaza_ruta_fuera_de_la_carpeta(self):
        archivo = Archivo(
            estudio=self.estudio,
            importacion=self.importacion,
            nombre_archivo="001",
            ruta_relativa="../otro_estudio/001",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="importaciones/1/otro_estudio/001",
            tamano=1024,
            hash_sha256="b" * 64,
            estado=EstadoArchivo.COMPLETO,
        )

        with self.assertRaises(ValidationError):
            archivo.save()

    def test_ruta_relativa_es_unica_dentro_de_la_importacion(self):
        self.crear_archivo()

        with self.assertRaises(IntegrityError):
            self.crear_archivo()
