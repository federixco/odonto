"""Elimina cargas de prueba tanto del almacenamiento como de MySQL."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.archivos.models import Archivo
from apps.archivos.services.storage import get_s3_client
from apps.core.enums import EstadoImportacion
from apps.estudios.models import ImportacionEstudio


class Command(BaseCommand):
    help = (
        "Limpia importaciones no confirmadas y sus objetos S3/MinIO. "
        "Solo está disponible con DEBUG=True."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Ejecuta la eliminación; sin esta opción solo muestra el resumen.",
        )
        parser.add_argument(
            "--incluir-confirmadas",
            action="store_true",
            help="Incluye importaciones ya confirmadas. Usar únicamente con datos de prueba.",
        )
        parser.add_argument(
            "--solo-base-datos",
            action="store_true",
            help="No intenta borrar objetos; sirve si el bucket ya fue vaciado manualmente.",
        )

    def handle(self, *args, **opciones):
        if not settings.DEBUG:
            raise CommandError(
                "Este comando está bloqueado porque DEBUG=False. No puede usarse en producción."
            )

        importaciones = ImportacionEstudio.objects.all()
        if not opciones["incluir_confirmadas"]:
            importaciones = importaciones.exclude(estado=EstadoImportacion.CONFIRMADA)

        archivos = Archivo.objects.filter(importacion__in=importaciones)
        cantidad_importaciones = importaciones.count()
        cantidad_archivos = archivos.count()
        claves = list(
            archivos.exclude(ruta_almacenamiento="").values_list(
                "ruta_almacenamiento", flat=True
            )
        )

        self.stdout.write(
            f"Se eliminarían {cantidad_importaciones} importaciones y "
            f"{cantidad_archivos} archivos de prueba."
        )
        if not opciones["confirmar"]:
            self.stdout.write(
                self.style.WARNING(
                    "Vista previa solamente. Repetí el comando con --confirmar para ejecutar."
                )
            )
            return

        if claves and not opciones["solo_base_datos"]:
            self._eliminar_objetos(claves)

        with transaction.atomic():
            archivos.delete()
            importaciones.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Limpieza completa: {cantidad_importaciones} importaciones y "
                f"{cantidad_archivos} archivos eliminados."
            )
        )

    @staticmethod
    def _eliminar_objetos(claves):
        """Borra claves en lotes; S3 acepta también objetos que ya no existen."""

        cliente = get_s3_client()
        for inicio in range(0, len(claves), 1000):
            lote = claves[inicio:inicio + 1000]
            respuesta = cliente.delete_objects(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Delete={
                    "Objects": [{"Key": clave} for clave in lote],
                    "Quiet": True,
                },
            )
            errores = respuesta.get("Errors", [])
            if errores:
                raise CommandError(
                    f"MinIO/S3 rechazó {len(errores)} objetos. No se modificó MySQL."
                )
