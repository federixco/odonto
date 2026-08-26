from django.contrib import admin

from .models import Archivo


@admin.register(Archivo)
class ArchivoAdmin(admin.ModelAdmin):
    """Consulta de metadatos, formato, estado e integridad de archivos."""

    list_display = ("nombre_archivo", "estudio", "formato", "categoria", "tamano", "estado", "created_at")
    list_filter = ("formato", "categoria", "estado")
    search_fields = ("nombre_archivo", "hash_sha256", "estudio__paciente__dni")
    autocomplete_fields = ("estudio", "archivo_reemplazado")
    readonly_fields = ("created_at",)
