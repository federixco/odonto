"""Mixins para control de acceso y autorizaciones en vistas basadas en clases."""

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied

from apps.core.enums import RolUsuario
from apps.estudios.models import Estudio


class RolRequeridoMixin(AccessMixin):
    """Verifica que el usuario autenticado tenga un rol específico."""

    rol_requerido = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
            
        if self.rol_requerido and request.user.rol != self.rol_requerido:
            raise PermissionDenied("No tienes permisos para acceder a esta vista.")
            
        return super().dispatch(request, *args, **kwargs)


class AdminRequeridoMixin(RolRequeridoMixin):
    rol_requerido = RolUsuario.ADMINISTRADOR


class OdontologoRequeridoMixin(RolRequeridoMixin):
    rol_requerido = RolUsuario.ODONTOLOGO


class PacienteRequeridoMixin(RolRequeridoMixin):
    rol_requerido = RolUsuario.PACIENTE


class EstudioAccesoMixin:
    """Verifica que el usuario tenga permiso explícito sobre el estudio solicitado."""

    def get_object(self, queryset=None):
        """Sobrescribe la obtención del objeto para inyectar validación."""
        obj = super().get_object(queryset)
        user = self.request.user

        if user.rol == RolUsuario.ADMINISTRADOR:
            # Administrador tiene acceso a todo
            return obj
            
        if user.rol == RolUsuario.ODONTOLOGO:
            from apps.core.enums import EstadoAcceso, EstadoEstudio
            
            autorizado_vigente = obj.autorizaciones.filter(
                odontologo__usuario=user,
                estado_acceso=EstadoAcceso.VIGENTE
            ).exists()
            
            if autorizado_vigente and obj.estado != EstadoEstudio.ELIMINADO:
                return obj
            
        if user.rol == RolUsuario.PACIENTE:
            # El paciente solo ve estudios de su propio perfil de paciente
            if hasattr(user, "paciente") and obj.paciente == user.paciente:
                return obj

        # Si llega acá, el usuario no tiene acceso válido.
        raise PermissionDenied("Acceso no autorizado a este estudio.")
