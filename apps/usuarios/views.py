"""Vistas de usuarios, dashboards y gestión de odontólogos."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from datetime import timedelta
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from apps.core.enums import EstadoAcceso, EstadoArchivo, EstadoCuenta, EstadoEstudio, RolUsuario
from apps.archivos.models import Archivo
from apps.core.mixins import AdminRequeridoMixin, OdontologoRequeridoMixin, PacienteRequeridoMixin
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente
from apps.usuarios.forms import (
    OdontologoAutoregistroForm,
    OdontologoCreacionAdminForm,
    OdontologoEdicionForm,
)
from apps.usuarios.models import Odontologo


@login_required
def redireccion_roles_view(request):
    """Enruta al usuario a su pantalla principal luego de iniciar sesión."""
    rol = request.user.rol
    if rol == RolUsuario.ADMINISTRADOR:
        return redirect("importacion_crear")
    if rol == RolUsuario.ODONTOLOGO:
        return redirect("dashboard_odontologo")
    if rol == RolUsuario.PACIENTE:
        return redirect("dashboard_paciente")
    return redirect("login")


# --- Dashboards por rol ---

class DashboardAdminView(AdminRequeridoMixin, View):
    """Conserva la URL anterior sin mostrar una pantalla intermedia."""

    def get(self, request, *args, **kwargs):
        return redirect("importacion_crear")


class DashboardOdontologoView(OdontologoRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_odontologo.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            odontologo = self.request.user.odontologo
        except Exception:
            odontologo = None

        context["odontologo"] = odontologo

        # Obtener autorizaciones vigentes y estudios publicados
        if odontologo:
            base_qs = Estudio.objects.filter(
                autorizaciones__odontologo=odontologo,
                autorizaciones__estado_acceso=EstadoAcceso.VIGENTE,
                estado=EstadoEstudio.PUBLICADO,
            ).select_related("paciente")
        else:
            base_qs = Estudio.objects.none()

        # Estadísticas / Métricas para el consultorio
        total_estudios = base_qs.count()
        total_pacientes = base_qs.values("paciente_id").distinct().count()
        hace_30_dias = timezone.now().date() - timedelta(days=30)
        estudios_recientes = base_qs.filter(fecha_estudio__gte=hace_30_dias).count()

        # Tipos de estudio disponibles para filtro
        tipos_disponibles = (
            base_qs.values_list("tipo", flat=True).distinct().order_by("tipo")
        )

        # Filtros por GET
        estudios = base_qs
        q = self.request.GET.get("q", "").strip()
        tipo = self.request.GET.get("tipo", "").strip()
        fecha_desde = self.request.GET.get("fecha_desde", "").strip()
        fecha_hasta = self.request.GET.get("fecha_hasta", "").strip()

        if q:
            estudios = estudios.filter(
                Q(paciente__nombre__icontains=q)
                | Q(paciente__apellido__icontains=q)
                | Q(paciente__dni__icontains=q)
            )

        if tipo:
            estudios = estudios.filter(tipo__iexact=tipo)

        if fecha_desde:
            try:
                estudios = estudios.filter(fecha_estudio__gte=fecha_desde)
            except Exception:
                pass

        if fecha_hasta:
            try:
                estudios = estudios.filter(fecha_estudio__lte=fecha_hasta)
            except Exception:
                pass

        estudios = estudios.annotate(
            cantidad_archivos=Count("archivos", filter=Q(archivos__estado=EstadoArchivo.COMPLETO)),
        ).order_by("-fecha_estudio", "-created_at", "-pk").prefetch_related(
            Prefetch("archivos", queryset=Archivo.objects.filter(estado=EstadoArchivo.COMPLETO)
                     .only("estudio_id", "formato").order_by("pk")[:4], to_attr="archivos_resumen"),
        )
        pagina = Paginator(estudios, 25).get_page(self.request.GET.get("page"))

        context.update({
            "estudios": pagina.object_list,
            "page_obj": pagina,
            "total_estudios": total_estudios,
            "total_pacientes": total_pacientes,
            "estudios_recientes": estudios_recientes,
            "tipos_disponibles": tipos_disponibles,
            "filtro_q": q,
            "filtro_tipo": tipo,
            "filtro_fecha_desde": fecha_desde,
            "filtro_fecha_hasta": fecha_hasta,
            "hay_filtros": bool(q or tipo or fecha_desde or fecha_hasta),
        })
        return context


class DashboardPacienteView(PacienteRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_paciente.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            paciente = self.request.user.paciente
        except Paciente.DoesNotExist:
            raise PermissionDenied("La cuenta no está vinculada a una ficha clínica.")

        estudios = Estudio.objects.filter(
            paciente=paciente,
            estado=EstadoEstudio.PUBLICADO,
        ).annotate(
            cantidad_archivos=Count("archivos", filter=Q(archivos__estado=EstadoArchivo.COMPLETO)),
        ).order_by("-fecha_estudio", "-created_at", "-pk")
        pagina = Paginator(estudios, 25).get_page(self.request.GET.get("page"))

        context["paciente"] = paciente
        context["estudios"] = pagina.object_list
        context["page_obj"] = pagina
        context["total_estudios"] = pagina.paginator.count
        return context



# --- Gestión de odontólogos (Admin) ---

class CrearOdontologoView(AdminRequeridoMixin, View):
    """Alta de odontólogo por el Administrador."""

    def _retorno_seguro(self, request):
        destino = request.POST.get("next") or request.GET.get("next", "")
        if destino and url_has_allowed_host_and_scheme(
            destino,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return destino
        return ""

    def get(self, request):
        form = OdontologoCreacionAdminForm()
        return render(
            request,
            "usuarios/odontologo_crear.html",
            {"form": form, "next_url": self._retorno_seguro(request)},
        )

    def post(self, request):
        form = OdontologoCreacionAdminForm(request.POST)
        if form.is_valid():
            odontologo = form.save()
            messages.success(request, f"Odontólogo {odontologo} creado exitosamente.")
            return redirect(self._retorno_seguro(request) or "odontologo_lista")
        return render(
            request,
            "usuarios/odontologo_crear.html",
            {"form": form, "next_url": self._retorno_seguro(request)},
        )


class ListaOdontologosView(AdminRequeridoMixin, ListView):
    """Listado de odontólogos con búsqueda por nombre, apellido o matrícula."""

    model = Odontologo
    template_name = "usuarios/odontologo_lista.html"
    context_object_name = "odontologos"
    paginate_by = 25

    def get_queryset(self):
        qs = Odontologo.objects.select_related("usuario").all()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                models_Q_nombre_apellido_matricula(q)
            )
        return qs.order_by("apellido", "nombre", "pk")

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
