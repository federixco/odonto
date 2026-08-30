"""Pruebas de publicación y eliminación lógica de estudios."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accesos.models import Autorizacion
from apps.archivos.models import Archivo
from apps.core.enums import (
    CategoriaArchivo,
    EstadoArchivo,
    EstadoCuenta,
    EstadoEstudio,
    FormatoArchivo,
    RolUsuario,
)
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo, Usuario

from apps.estudios.models import Estudio


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

        with self.assertRaises(ValidationError):
            self.estudio.publicar()

    def test_publica_estudio_completo_y_autorizado(self):
        self.crear_archivo(EstadoArchivo.COMPLETO)

        self.estudio.publicar()
        self.estudio.refresh_from_db()

        self.assertEqual(self.estudio.estado, EstadoEstudio.PUBLICADO)
        self.assertIsNotNone(self.estudio.fecha_publicacion)

    def test_delete_realiza_eliminacion_logica(self):
        estudio_id = self.estudio.pk

        self.estudio.delete()

        estudio = Estudio.objects.get(pk=estudio_id)
        self.assertEqual(estudio.estado, EstadoEstudio.ELIMINADO)
