from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mixins import AdminRequeridoMixin
from .forms import EstudioForm
from .models import Estudio

class CrearEstudioView(AdminRequeridoMixin, View):
    """
    Vista para que el administrador inicie un nuevo estudio.
    Crea el Estudio en estado BORRADOR y redirige al detalle
    para continuar con la subida de archivos (Etapa 3).
    """
    def get(self, request):
        return render(request, "estudios/estudio_crear.html", {"form": EstudioForm()})

    def post(self, request):
        form = EstudioForm(request.POST)
        if form.is_valid():
            estudio = form.save(commit=False)
            # El estado por defecto es BORRADOR
            estudio.save()
            messages.success(request, f"Estudio creado. Por favor subí los archivos.")
            # Redirigir a la vista de subida de archivos (detalle o carga)
            return redirect("estudio_detalle", pk=estudio.pk)
        return render(request, "estudios/estudio_crear.html", {"form": form})

class DetalleEstudioView(AdminRequeridoMixin, DetailView):
    """Vista temporal de detalle para ver y subir archivos."""
    model = Estudio
    template_name = "estudios/estudio_detalle.html"
    context_object_name = "estudio"
