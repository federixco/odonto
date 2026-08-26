from django.apps import AppConfig


class EstudiosConfig(AppConfig):
    """Configuración de estudios e información clínica asociada."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.estudios"
    label = "estudios"
