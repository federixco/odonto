"""Estudio odontológico asociado obligatoriamente a un paciente."""

from django.db import models

from apps.core.enums import EstadoEstudio


# Estudio perteneciente a un paciente y compuesto por uno o más archivos.
class Estudio(models.Model):
    """Conjunto de imágenes y archivos de un paciente."""

    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.PROTECT, related_name="estudios", db_column="id_paciente")
    tipo = models.CharField(max_length=100)
    fecha_estudio = models.DateField()
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=EstadoEstudio.choices, default=EstadoEstudio.BORRADOR)
    fecha_publicacion = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "estudio"
        verbose_name = "estudio"
        verbose_name_plural = "estudios"
        ordering = ["-fecha_estudio", "-created_at"]

    def __str__(self):
        return f"Estudio {self.pk} - {self.paciente}"
