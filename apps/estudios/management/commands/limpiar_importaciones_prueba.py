"""Elimina cargas de prueba tanto del almacenamiento como de MySQL."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from urllib.parse import urlparse

from apps.archivos.models import Archivo
from apps.archivos.services.storage import abortar_multipart_upload, get_s3_client
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

        # DEBUG por sí solo no garantiza que .env apunte al entorno de prueba.
        locales = {"localhost", "127.0.0.1", "::1"}
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.sqlite3" and db.get("HOST") not in locales:
            raise CommandError("La limpieza de prueba requiere una base de datos local.")
        if not opciones["solo_base_datos"] and urlparse(settings.AWS_S3_ENDPOINT_URL or "").hostname not in locales:
            raise CommandError("La limpieza de prueba requiere un endpoint S3 local explícito.")

        if claves and not opciones["solo_base_datos"]:
            for archivo in archivos.exclude(upload_id__isnull=True).exclude(upload_id="").iterator():
                if not abortar_multipart_upload(archivo.ruta_almacenamiento, archivo.upload_id):
                    raise CommandError("No se confirmó el aborto multipartes. No se modificó la base de datos.")
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
        try:
            for inicio in range(0, len(claves), 1000):
                lote = claves[inicio:inicio + 1000]
                respuesta = cliente.delete_objects(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Delete={"Objects": [{"Key": clave} for clave in lote], "Quiet": True},
                )
                if respuesta.get("Errors"):
                    raise CommandError("MinIO/S3 rechazó objetos. No se modificó MySQL.")
        finally:
            cliente.close()
