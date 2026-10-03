"""Worker de análisis. Ejecutar separado de runserver; no depende de SQLite."""
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection, OperationalError
from apps.estudios.services.trabajos import procesar_uno
from apps.estudios.services.cancelacion import limpiar_cancelaciones


class Command(BaseCommand):
    help = "Procesa la cola de análisis de importaciones (MySQL + S3)."

    def add_arguments(self, parser):
        parser.add_argument("--una-vez", action="store_true")

    def handle(self, *args, **options):
        if connection.vendor != "mysql":
            raise CommandError("El worker requiere la configuración MySQL del proyecto.")
        self.stdout.write("Worker activo. Ctrl+C para detener.")
        try:
            while True:
                close_old_connections()
                try:
                    procesado = procesar_uno()
                    limpiar_cancelaciones()
                except OperationalError:
                    if options["una_vez"]:
                        raise
                    self.stderr.write("MySQL no está disponible; reintento en 5 segundos.")
                    connection.close()
                    time.sleep(5)
                    continue
                if options["una_vez"]:
                    return
                if not procesado:
                    time.sleep(2)
        except KeyboardInterrupt:
            self.stdout.write("Worker detenido; las reservas pendientes se recuperarán.")
