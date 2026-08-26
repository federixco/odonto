from django.contrib import admin

from .models import LogActividad


@admin.register(LogActividad)
class LogActividadAdmin(admin.ModelAdmin):
    """Vista de solo lectura para preservar la trazabilidad registrada."""

    list_display = ("fecha_hora", "tipo_evento", "usuario", "estudio", "resultado")
    list_filter = ("tipo_evento", "fecha_hora")
    search_fields = ("usuario__username", "estudio__paciente__dni", "resultado", "detalles")
    readonly_fields = ("usuario", "estudio", "tipo_evento", "fecha_hora", "resultado", "detalles")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
