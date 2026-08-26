from django.contrib import admin

from .models import Estudio


@admin.register(Estudio)
class EstudioAdmin(admin.ModelAdmin):
    """Administración de estudios asociados obligatoriamente a pacientes."""

    list_display = ("id", "paciente", "tipo", "fecha_estudio", "estado", "fecha_publicacion")
    list_filter = ("estado", "tipo", "fecha_estudio")
    search_fields = ("paciente__nombre", "paciente__apellido", "paciente__dni", "tipo")
    autocomplete_fields = ("paciente",)
    date_hierarchy = "fecha_estudio"
