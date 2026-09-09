from django.urls import path
from .views import IniciarArchivoView, CompletarArchivoView, CancelarArchivoView

urlpatterns = [
    # Se espera que el prefijo sea /estudios/<estudio_id>/archivos/iniciar/
    # Pero las urls se incluyen desde config/urls.py
    path("iniciar/<int:estudio_id>/", IniciarArchivoView.as_view(), name="archivo_iniciar"),
    path("completar/<int:archivo_id>/", CompletarArchivoView.as_view(), name="archivo_completar"),
    path("cancelar/<int:archivo_id>/", CancelarArchivoView.as_view(), name="archivo_cancelar"),
]
