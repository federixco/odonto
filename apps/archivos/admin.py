from django.contrib import admin

from .models import Archivo


@admin.register(Archivo)
class ArchivoAdmin(admin.ModelAdmin):
    """Consulta de metadatos, formato, estado e integridad de archivos."""

    list_display = (
        "nombre_archivo",
        "estudio",
        "importacion",
        "formato",
        "categoria",
        "tamano",
        "estado",
        "created_at",
    )
    list_filter = ("formato", "categoria", "estado")
    search_fields = (
        "nombre_archivo",
        "ruta_relativa",
        "hash_sha256",
        "sop_instance_uid",
        "estudio__paciente__dni",
    )
    autocomplete_fields = (
        "estudio",
        "importacion",
        "serie_dicom",
        "archivo_reemplazado",
    )
    readonly_fields = ("created_at", "updated_at")
