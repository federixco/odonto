"""Registro inmutable de eventos relevantes para la trazabilidad."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.enums import TipoEvento


class LogActividadQuerySet(models.QuerySet):
    """Impide modificaciones o eliminaciones masivas de la auditoría."""

    def update(self, **kwargs):
        raise ValidationError("Los registros de actividad son inmutables.")

    def delete(self):
        raise ValidationError("Los registros de actividad no pueden eliminarse.")


class LogActividad(models.Model):
    """Evento inmutable realizado por un usuario identificado."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="logs_actividad", db_column="id_usuario")
    estudio = models.ForeignKey("estudios.Estudio", null=True, blank=True, on_delete=models.SET_NULL, related_name="logs_actividad", db_column="id_estudio")
    tipo_evento = models.CharField(max_length=20, choices=TipoEvento.choices)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    resultado = models.CharField(max_length=255)
    detalles = models.TextField(blank=True)

    objects = LogActividadQuerySet.as_manager()

    class Meta:
        db_table = "log_actividad"
        verbose_name = "registro de actividad"
        verbose_name_plural = "registros de actividad"
        ordering = ["-fecha_hora"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tipo_evento__in=TipoEvento.values),
                name="ck_log_tipo_evento_valido",
            ),
        ]

    def __str__(self):
        return f"{self.tipo_evento} - {self.fecha_hora:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        """Permite crear el evento una vez, pero nunca modificarlo."""
        if not self._state.adding:
            raise ValidationError("Los registros de actividad son inmutables.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Preserva permanentemente la evidencia de auditoría."""
        raise ValidationError("Los registros de actividad no pueden eliminarse.")
