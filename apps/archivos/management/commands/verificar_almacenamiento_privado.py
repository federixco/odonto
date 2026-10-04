"""Prueba de lectura: no crea, modifica ni elimina objetos ni registros."""

from contextlib import ExitStack
from urllib.parse import urlsplit

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.archivos.models import Archivo
from apps.archivos.services.storage import get_s3_client
from apps.core.enums import EstadoArchivo


def _exigir_denegacion(operacion, mensaje_publico):
    """Solo una denegación explícita es evidencia; un 404 no demuestra privacidad."""
    try:
        respuesta = operacion()
    except ClientError as error:
        if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 403:
            return
        raise CommandError("Comprobación inconclusa: no se recibió una denegación HTTP 403.") from None
    if respuesta.get("Body") is not None:
        respuesta["Body"].close()
    raise CommandError(mensaje_publico)


class Command(BaseCommand):
    help = "Verifica que no se pueda listar el bucket ni leer un archivo de prueba sin autenticación."

    def add_arguments(self, parser):
        parser.add_argument("--archivo-id", type=int, required=True)

    def handle(self, *args, **options):
        try:
            endpoint = settings.AWS_S3_ENDPOINT_URL
            if endpoint and urlsplit(endpoint).scheme != "https":
                raise CommandError("Esta comprobación de despliegue requiere un endpoint HTTPS.")
            archivo = Archivo.objects.filter(
                pk=options["archivo_id"], estado=EstadoArchivo.COMPLETO, tamano__gt=0,
            ).first()
            if archivo is None:
                raise CommandError("Elegí un archivo completo, existente y no vacío para la prueba.")

            with ExitStack() as recursos:
                privado = get_s3_client()
                recursos.callback(privado.close)
                bucket = settings.AWS_STORAGE_BUCKET_NAME
                privado.head_bucket(Bucket=bucket)
                privado.head_object(Bucket=bucket, Key=archivo.ruta_almacenamiento)
                anonimo = get_s3_client(anonimo=True)
                recursos.callback(anonimo.close)
                _exigir_denegacion(
                    lambda: anonimo.list_objects_v2(Bucket=bucket, MaxKeys=1),
                    "El bucket permite listar objetos sin autenticación: corregí sus permisos.",
                )
                _exigir_denegacion(
                    lambda: anonimo.get_object(
                        Bucket=bucket, Key=archivo.ruta_almacenamiento, Range="bytes=0-0",
                    ),
                    "El archivo de prueba permite lectura anónima: corregí sus permisos.",
                )
        except CommandError:
            raise
        except Exception:
            # No volcar errores del SDK: pueden incluir claves de objetos o URLs.
            raise CommandError("No se pudo completar la verificación; revisá conexión y permisos del proveedor.") from None
        self.stdout.write(self.style.SUCCESS(
            "Acceso anónimo rechazado para listado y archivo de prueba. "
            "No sustituye una revisión completa de las políticas del bucket."
        ))
