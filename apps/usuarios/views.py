from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import path
from django.views.generic import TemplateView

from apps.core.enums import RolUsuario
from apps.core.mixins import AdminRequeridoMixin, OdontologoRequeridoMixin, PacienteRequeridoMixin


@login_required
def redireccion_roles_view(request):
    """Enruta al usuario a su dashboard principal luego de iniciar sesión."""
    rol = request.user.rol
    if rol == RolUsuario.ADMINISTRADOR:
        return redirect("dashboard_admin")
    elif rol == RolUsuario.ODONTOLOGO:
        return redirect("dashboard_odontologo")
    elif rol == RolUsuario.PACIENTE:
        return redirect("dashboard_paciente")
    return redirect("login")


# --- Vistas de prueba para validar restricción de roles ---

class DashboardAdminView(AdminRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_admin.html"


class DashboardOdontologoView(OdontologoRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_odontologo.html"


class DashboardPacienteView(PacienteRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_paciente.html"
