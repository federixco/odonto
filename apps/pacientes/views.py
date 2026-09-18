"""Vistas administrativas de fichas clínicas de pacientes."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mixins import AdminRequeridoMixin

from .forms import CrearAccesoPacienteForm, PacienteForm
from .models import Paciente


class ListaPacientesView(AdminRequeridoMixin, ListView):
    model = Paciente
    template_name = "pacientes/paciente_lista.html"
    context_object_name = "pacientes"

    def get_queryset(self):
        queryset = Paciente.objects.select_related("usuario")
        busqueda = self.request.GET.get("q", "").strip()
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda)
                | Q(apellido__icontains=busqueda)
                | Q(dni__icontains=busqueda)
            )
        return queryset.order_by("apellido", "nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["busqueda"] = self.request.GET.get("q", "")
        return context


class CrearPacienteView(AdminRequeridoMixin, View):
    def get(self, request):
        return render(request, "pacientes/paciente_crear.html", {"form": PacienteForm()})

    def post(self, request):
        form = PacienteForm(request.POST)
        if form.is_valid():
            paciente = form.save()
            messages.success(request, f"Ficha de {paciente} creada exitosamente.")
            return redirect("paciente_detalle", pk=paciente.pk)
        return render(request, "pacientes/paciente_crear.html", {"form": form})


class DetallePacienteView(AdminRequeridoMixin, DetailView):
    model = Paciente
    template_name = "pacientes/paciente_detalle.html"
    context_object_name = "paciente"

    def get_queryset(self):
        return Paciente.objects.select_related("usuario").prefetch_related("estudios")


class EditarPacienteView(AdminRequeridoMixin, View):
    def get(self, request, pk):
        paciente = get_object_or_404(Paciente.objects.select_related("usuario"), pk=pk)
        return render(
            request,
            "pacientes/paciente_editar.html",
            {"paciente": paciente, "form": PacienteForm(paciente=paciente, instance=paciente)},
        )

    def post(self, request, pk):
        paciente = get_object_or_404(Paciente.objects.select_related("usuario"), pk=pk)
        form = PacienteForm(request.POST, paciente=paciente, instance=paciente)
        if form.is_valid():
            paciente = form.save()
            messages.success(request, f"Ficha de {paciente} actualizada.")
            return redirect("paciente_detalle", pk=paciente.pk)
        return render(request, "pacientes/paciente_editar.html", {"paciente": paciente, "form": form})


class CrearAccesoPacienteView(AdminRequeridoMixin, View):
    def get(self, request, pk):
        paciente = get_object_or_404(Paciente.objects.select_related("usuario"), pk=pk)
        if paciente.usuario_id:
            messages.info(request, "La ficha ya tiene una cuenta de acceso vinculada.")
            return redirect("paciente_detalle", pk=paciente.pk)
        return render(
            request,
            "pacientes/paciente_acceso_crear.html",
            {"paciente": paciente, "form": CrearAccesoPacienteForm(paciente=paciente)},
        )

    def post(self, request, pk):
        paciente = get_object_or_404(Paciente.objects.select_related("usuario"), pk=pk)
        if paciente.usuario_id:
            messages.info(request, "La ficha ya tiene una cuenta de acceso vinculada.")
            return redirect("paciente_detalle", pk=paciente.pk)
        form = CrearAccesoPacienteForm(request.POST, paciente=paciente)
        if form.is_valid():
            form.save()
            messages.success(request, f"Cuenta de acceso creada para {paciente}.")
            return redirect("paciente_detalle", pk=paciente.pk)
        return render(request, "pacientes/paciente_acceso_crear.html", {"paciente": paciente, "form": form})
