from django.contrib import admin

from .models import Estudio, ImportacionEstudio, SerieDicom


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
        "formato_detectado",
        "estado",
        "cantidad_archivos",
        "created_at",
    )
    list_filter = ("formato_detectado", "estado", "nivel_confianza")
    search_fields = (
        "nombre_carpeta",
        "identificador_paciente_detectado",
        "study_instance_uid",
    )
    autocomplete_fields = ("estudio", "iniciada_por", "paciente_sugerido")
    readonly_fields = ("created_at", "updated_at", "finalizada_at")


@admin.register(SerieDicom)
class SerieDicomAdmin(admin.ModelAdmin):
    """Consulta de las series descubiertas dentro de una importación DICOM."""

    list_display = (
        "id",
        "importacion",
        "modalidad",
        "numero_serie",
        "cantidad_archivos",
    )
    search_fields = ("series_instance_uid", "descripcion")
    autocomplete_fields = ("importacion",)
