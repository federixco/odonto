from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    """Configuración de la trazabilidad de acciones del sistema."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auditoria"
    label = "auditoria"
