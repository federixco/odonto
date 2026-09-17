from django.urls import path
from .views import (
    CancelarArchivoView,
    CompletarArchivoView,
    EliminarArchivoView,
    IniciarArchivoView,
    MarcarArchivoIncorrectoView,
)

urlpatterns = [
    # Se espera que el prefijo sea /estudios/<estudio_id>/archivos/iniciar/
    # Pero las urls se incluyen desde config/urls.py
    path("iniciar/<int:estudio_id>/", IniciarArchivoView.as_view(), name="archivo_iniciar"),
    path("completar/<int:archivo_id>/", CompletarArchivoView.as_view(), name="archivo_completar"),
    path("cancelar/<int:archivo_id>/", CancelarArchivoView.as_view(), name="archivo_cancelar"),
    path("<int:archivo_id>/marcar-incorrecto/", MarcarArchivoIncorrectoView.as_view(), name="archivo_marcar_incorrecto"),
    path("eliminar/<int:archivo_id>/", EliminarArchivoView.as_view(), name="archivo_eliminar"),
]
