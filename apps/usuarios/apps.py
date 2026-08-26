from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    """Configuración de autenticación y perfiles profesionales."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.usuarios"
    label = "usuarios"
