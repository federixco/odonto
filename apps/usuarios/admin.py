from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Odontologo, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Administración de credenciales, rol y estado de cada cuenta."""

    list_display = ("username", "email", "rol", "estado", "is_staff", "is_active")
    list_filter = ("rol", "estado", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name", "telefono")
    fieldsets = UserAdmin.fieldsets + (
        ("Datos de SISETMA", {"fields": ("telefono", "rol", "estado")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos de SISETMA", {"fields": ("email", "telefono", "rol", "estado")}),
    )


@admin.register(Odontologo)
class OdontologoAdmin(admin.ModelAdmin):
    """Consulta y edición del perfil profesional del derivante."""

    list_display = ("apellido", "nombre", "matricula", "usuario")
    search_fields = ("apellido", "nombre", "matricula", "usuario__email")
    autocomplete_fields = ("usuario",)
