from django.contrib import admin

from .models import Autorizacion


@admin.register(Autorizacion)
class AutorizacionAdmin(admin.ModelAdmin):
    """Gestión de permisos revocables entre odontólogos y estudios."""

    list_display = ("odontologo", "estudio", "estado_acceso", "fecha_autorizacion", "fecha_revocacion")
    list_filter = ("estado_acceso", "fecha_autorizacion")
    search_fields = ("odontologo__apellido", "odontologo__matricula", "estudio__paciente__dni")
    autocomplete_fields = ("odontologo", "estudio", "revocado_por")
    readonly_fields = ("fecha_autorizacion",)
