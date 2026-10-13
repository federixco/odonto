"""Context processors para el módulo de usuarios y notificaciones administrativas."""

from apps.core.enums import EstadoCuenta
from apps.usuarios.models import Odontologo


def notificaciones_admin(request):
    """Provee a las plantillas administrativas el conteo de odontólogos pendientes de habilitación."""
    user = getattr(request, "user", None)
    if user and user.is_authenticated and getattr(user, "rol", None) == "ADMINISTRADOR":
        pendientes = Odontologo.objects.filter(usuario__estado=EstadoCuenta.PENDIENTE).count()
        return {
            "odontologos_pendientes_count": pendientes,
        }
    return {
        "odontologos_pendientes_count": 0,
    }
