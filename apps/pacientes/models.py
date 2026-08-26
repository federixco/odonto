"""Paciente clínico, con cuenta web opcional."""

from django.conf import settings
from django.db import models


# Registro clínico del paciente; puede existir sin cuenta web.
class Paciente(models.Model):
    """Persona a la que pertenecen los estudios odontológicos.

    El perfil se crea al cargar un estudio y no requiere que el paciente use
    la plataforma. La relación con Usuario es opcional para el caso especial
    en que el paciente solicite acceso directo a sus propios estudios.
    """

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="paciente", db_column="id_usuario")
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=20, unique=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    obra_social = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "paciente"
        verbose_name = "paciente"
        verbose_name_plural = "pacientes"

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"
