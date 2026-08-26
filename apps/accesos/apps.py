from django.apps import AppConfig


class AccesosConfig(AppConfig):
    """Configuración de autorizaciones de estudios a odontólogos."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accesos"
    label = "accesos"
