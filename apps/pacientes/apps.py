from django.apps import AppConfig


class PacientesConfig(AppConfig):
    """Configuración del registro clínico de pacientes."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pacientes"
    label = "pacientes"
