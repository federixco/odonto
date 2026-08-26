from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuración de elementos compartidos del dominio."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
