from django.apps import AppConfig


class ArchivosConfig(AppConfig):
    """Configuración de archivos digitales de cada estudio."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.archivos"
    label = "archivos"
