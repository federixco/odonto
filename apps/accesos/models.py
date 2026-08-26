"""Autorizaciones temporales o revocables para compartir estudios."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.enums import EstadoAcceso


# Permiso revocable mediante el cual un odontólogo recibe un estudio.
class Autorizacion(models.Model):
    """Permiso de un odontólogo para acceder a un estudio."""

    odontologo = models.ForeignKey("usuarios.Odontologo", on_delete=models.PROTECT, related_name="autorizaciones", db_column="id_odontologo")
    estudio = models.ForeignKey("estudios.Estudio", on_delete=models.CASCADE, related_name="autorizaciones", db_column="id_estudio")
    estado_acceso = models.CharField(max_length=15, choices=EstadoAcceso.choices, default=EstadoAcceso.VIGENTE)
    fecha_autorizacion = models.DateTimeField(auto_now_add=True)
    fecha_revocacion = models.DateTimeField(null=True, blank=True)
    revocado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="autorizaciones_revocadas")

    class Meta:
        db_table = "autorizacion"
        verbose_name = "autorización"
        verbose_name_plural = "autorizaciones"
        constraints = [models.UniqueConstraint(fields=["odontologo", "estudio"], name="uq_autorizacion_odontologo_estudio")]

    def esta_vigente(self):
        return self.estado_acceso == EstadoAcceso.VIGENTE and self.estudio.estado != "ELIMINADO"

    def revocar(self, usuario=None):
        self.estado_acceso = EstadoAcceso.REVOCADO
        self.fecha_revocacion = timezone.now()
        self.revocado_por = usuario
        self.save(update_fields=["estado_acceso", "fecha_revocacion", "revocado_por"])
