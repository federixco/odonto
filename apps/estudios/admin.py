from django.contrib import admin

from .models import Estudio, ImportacionEstudio


@admin.register(Estudio)
class EstudioAdmin(admin.ModelAdmin):
    """Administración de estudios asociados obligatoriamente a pacientes."""

    list_display = ("id", "paciente", "tipo", "fecha_estudio", "estado", "fecha_publicacion")
    list_filter = ("estado", "tipo", "fecha_estudio")
    search_fields = ("paciente__nombre", "paciente__apellido", "paciente__dni", "tipo")
    autocomplete_fields = ("paciente",)
    date_hierarchy = "fecha_estudio"


@admin.register(ImportacionEstudio)
class ImportacionEstudioAdmin(admin.ModelAdmin):
    """Seguimiento técnico de carpetas cargadas y datos detectados."""

    list_display = (
        "id",
        "nombre_carpeta",
        "estado",
        "cantidad_archivos",
        "created_at",
    )
    list_filter = ("estado",)
    search_fields = (
        "nombre_carpeta",
        "datos_detectados",
    )
    autocomplete_fields = ("estudio", "iniciada_por", "paciente_sugerido")
    readonly_fields = ("created_at", "updated_at")
