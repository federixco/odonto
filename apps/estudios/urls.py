from django.urls import path
from .views import CrearEstudioView, DetalleEstudioView

urlpatterns = [
    path("crear/", CrearEstudioView.as_view(), name="estudio_crear"),
    path("<int:pk>/", DetalleEstudioView.as_view(), name="estudio_detalle"),
]
