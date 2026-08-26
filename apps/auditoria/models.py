"""Registro inmutable de eventos relevantes para la trazabilidad."""

from django.conf import settings
from django.db import models

from apps.core.enums import TipoEvento


# Evidencia de trazabilidad: quién hizo qué, cuándo y sobre qué estudio.
class LogActividad(models.Model):
    """Evento realizado por un usuario y, opcionalmente, sobre un estudio."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="logs_actividad", db_column="id_usuario")
    estudio = models.ForeignKey("estudios.Estudio", null=True, blank=True, on_delete=models.SET_NULL, related_name="logs_actividad", db_column="id_estudio")
    tipo_evento = models.CharField(max_length=20, choices=TipoEvento.choices)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    resultado = models.CharField(max_length=255)
    detalles = models.TextField(blank=True)

    class Meta:
        db_table = "log_actividad"
        verbose_name = "registro de actividad"
        verbose_name_plural = "registros de actividad"
        ordering = ["-fecha_hora"]

    def __str__(self):
        return f"{self.tipo_evento} - {self.fecha_hora:%Y-%m-%d %H:%M}"
