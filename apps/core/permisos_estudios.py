"""Una sola política para lectura privada; visualizar no autoriza exportar."""
from django.core.exceptions import PermissionDenied
from .enums import EstadoAcceso, EstadoCuenta, EstadoEstudio, RolUsuario


def comprobar_acceso_estudio(usuario, estudio, *, descargar=False):
    if not usuario.is_authenticated or not usuario.is_active or usuario.estado != EstadoCuenta.HABILITADA:
        raise PermissionDenied("La cuenta no está habilitada.")
    if estudio.estado == EstadoEstudio.ELIMINADO:
        raise PermissionDenied("El estudio no está disponible.")
    if usuario.rol == RolUsuario.ADMINISTRADOR:
        return
    if estudio.estado != EstadoEstudio.PUBLICADO:
        raise PermissionDenied("El estudio no está publicado.")
    if usuario.rol == RolUsuario.ODONTOLOGO and estudio.autorizaciones.filter(
        odontologo__usuario=usuario, estado_acceso=EstadoAcceso.VIGENTE,
    ).exists():
        return
    if not descargar and usuario.rol == RolUsuario.PACIENTE and estudio.paciente.usuario_id == usuario.pk:
        return
    raise PermissionDenied("No tenés permiso para realizar esta acción sobre el estudio.")
