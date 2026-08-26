from django.contrib import admin

from .models import Paciente


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    """Administración del registro clínico y su cuenta web opcional."""

    list_display = ("apellido", "nombre", "dni", "fecha_nacimiento", "usuario")
    search_fields = ("apellido", "nombre", "dni")
    autocomplete_fields = ("usuario",)
