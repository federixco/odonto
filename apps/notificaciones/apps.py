from django.apps import AppConfig


class NotificacionesConfig(AppConfig):
    """Punto de extensión para avisos por correo y futuros canales."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notificaciones"
    label = "notificaciones"
