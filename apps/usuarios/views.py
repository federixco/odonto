"""Vistas de usuarios, dashboards y gestión de odontólogos."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.core.enums import EstadoCuenta, RolUsuario
from apps.core.mixins import AdminRequeridoMixin, OdontologoRequeridoMixin, PacienteRequeridoMixin
from apps.usuarios.forms import (
    OdontologoAutoregistroForm,
    OdontologoCreacionAdminForm,
    OdontologoEdicionForm,
)
from apps.usuarios.models import Odontologo


@login_required
def redireccion_roles_view(request):
    """Enruta al usuario a su dashboard principal luego de iniciar sesión."""
    rol = request.user.rol
    if rol == RolUsuario.ADMINISTRADOR:
        return redirect("dashboard_admin")
    if rol == RolUsuario.ODONTOLOGO:
        return redirect("dashboard_odontologo")
    if rol == RolUsuario.PACIENTE:
        return redirect("dashboard_paciente")
    return redirect("login")


# --- Dashboards por rol ---

class DashboardAdminView(AdminRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_admin.html"


class DashboardOdontologoView(OdontologoRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_odontologo.html"


class DashboardPacienteView(PacienteRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_paciente.html"


# --- Gestión de odontólogos (Admin) ---

class CrearOdontologoView(AdminRequeridoMixin, View):
    """Alta de odontólogo por el Administrador."""

    def get(self, request):
        form = OdontologoCreacionAdminForm()
        return render(request, "usuarios/odontologo_crear.html", {"form": form})

    def post(self, request):
        form = OdontologoCreacionAdminForm(request.POST)
        if form.is_valid():
            odontologo = form.save()
            messages.success(request, f"Odontólogo {odontologo} creado exitosamente.")
            return redirect("odontologo_lista")
        return render(request, "usuarios/odontologo_crear.html", {"form": form})


class ListaOdontologosView(AdminRequeridoMixin, ListView):
    """Listado de odontólogos con búsqueda por nombre, apellido o matrícula."""

    model = Odontologo
    template_name = "usuarios/odontologo_lista.html"
    context_object_name = "odontologos"

    def get_queryset(self):
        qs = Odontologo.objects.select_related("usuario").all()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                models_Q_nombre_apellido_matricula(q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["busqueda"] = self.request.GET.get("q", "")
        return context


def models_Q_nombre_apellido_matricula(q):
    """Construye un filtro OR para búsqueda de odontólogos."""
    from django.db.models import Q
    return (
        Q(nombre__icontains=q)
        | Q(apellido__icontains=q)
        | Q(matricula__icontains=q)
        | Q(usuario__email__icontains=q)
    )


class DetalleOdontologoView(AdminRequeridoMixin, DetailView):
    """Detalle de un odontólogo específico."""

    model = Odontologo
    template_name = "usuarios/odontologo_detalle.html"
    context_object_name = "odontologo"

    def get_queryset(self):
        return Odontologo.objects.select_related("usuario")


class EditarOdontologoView(AdminRequeridoMixin, View):
    """Edición de datos del odontólogo por el Administrador."""

    def get(self, request, pk):
        odontologo = get_object_or_404(Odontologo.objects.select_related("usuario"), pk=pk)
        form = OdontologoEdicionForm(odontologo=odontologo)
        return render(request, "usuarios/odontologo_editar.html", {"form": form, "odontologo": odontologo})

    def post(self, request, pk):
        odontologo = get_object_or_404(Odontologo.objects.select_related("usuario"), pk=pk)
        form = OdontologoEdicionForm(request.POST, odontologo=odontologo)
        if form.is_valid():
            form.save()
            messages.success(request, f"Datos de {odontologo} actualizados.")
            return redirect("odontologo_detalle", pk=pk)
        return render(request, "usuarios/odontologo_editar.html", {"form": form, "odontologo": odontologo})


class HabilitarOdontologoView(AdminRequeridoMixin, View):
    """Cambia el estado de la cuenta a HABILITADA."""

    def post(self, request, pk):
        odontologo = get_object_or_404(Odontologo.objects.select_related("usuario"), pk=pk)
        usuario = odontologo.usuario
        usuario.estado = EstadoCuenta.HABILITADA
        usuario.save(update_fields=["estado", "is_active", "updated_at"])
        messages.success(request, f"Cuenta de {odontologo} habilitada.")
        return redirect("odontologo_detalle", pk=pk)


class DeshabilitarOdontologoView(AdminRequeridoMixin, View):
    """Cambia el estado de la cuenta a DESHABILITADA."""

    def post(self, request, pk):
        odontologo = get_object_or_404(Odontologo.objects.select_related("usuario"), pk=pk)
        usuario = odontologo.usuario
        usuario.estado = EstadoCuenta.DESHABILITADA
        usuario.save(update_fields=["estado", "is_active", "updated_at"])
        messages.success(request, f"Cuenta de {odontologo} deshabilitada.")
        return redirect("odontologo_detalle", pk=pk)


# --- Autorregistro público ---

class AutoregistroOdontologoView(View):
    """Autorregistro público de odontólogo (estado PENDIENTE)."""

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("redireccion_roles")
        form = OdontologoAutoregistroForm()
        return render(request, "usuarios/odontologo_autoregistro.html", {"form": form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("redireccion_roles")
        form = OdontologoAutoregistroForm(request.POST)
        if form.is_valid():
            form.save()
            messages.info(
                request,
                "Tu cuenta fue creada exitosamente. Un administrador debe habilitarla antes de que puedas ingresar.",
            )
            return redirect("login")
        return render(request, "usuarios/odontologo_autoregistro.html", {"form": form})
