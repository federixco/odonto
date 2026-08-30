"""Mixins para control de acceso y autorizaciones en vistas basadas en clases."""

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied

from apps.core.enums import EstadoAcceso, EstadoEstudio, RolUsuario


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


class EstudioAccesoMixin(AccessMixin):
    """Verifica que el usuario tenga permiso explícito sobre el estudio solicitado."""

    def dispatch(self, request, *args, **kwargs):
        """Exige autenticación antes de consultar el objeto solicitado."""
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        """Sobrescribe la obtención del objeto para inyectar validación."""
        obj = super().get_object(queryset)
        user = self.request.user

        if user.rol == RolUsuario.ADMINISTRADOR:
            # El administrador gestiona también borradores, correcciones y bajas.
            return obj

        if user.rol == RolUsuario.ODONTOLOGO:
            autorizado_vigente = obj.autorizaciones.filter(
                odontologo__usuario=user,
                estado_acceso=EstadoAcceso.VIGENTE,
            ).exists()

            if autorizado_vigente and obj.estado == EstadoEstudio.PUBLICADO:
                return obj

        if user.rol == RolUsuario.PACIENTE:
            # El paciente solo ve estudios publicados de su propio perfil.
            if (
                hasattr(user, "paciente")
                and obj.paciente_id == user.paciente.id
                and obj.estado == EstadoEstudio.PUBLICADO
            ):
                return obj

        # Si llega acá, el usuario no tiene acceso válido.
        raise PermissionDenied("Acceso no autorizado a este estudio.")
