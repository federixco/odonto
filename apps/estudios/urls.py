from django.urls import path
from .views import (AnalizarImportacionView, CompletarArchivoImportadoView,
                    ConfirmarImportacionView, CrearEstudioView,
                    CrearImportacionView, DetalleEstudioView,
                    DetalleImportacionView, IniciarArchivoImportadoView,
                    IniciarImportacionView, RegistrarPacienteDetectadoView)

urlpatterns = [
    path("crear/", CrearEstudioView.as_view(), name="estudio_crear"),
    path("importar/", CrearImportacionView.as_view(), name="importacion_crear"),
    path("importaciones/iniciar/", IniciarImportacionView.as_view(), name="importacion_iniciar"),
    path("importaciones/<int:importacion_id>/archivos/iniciar/", IniciarArchivoImportadoView.as_view(), name="importacion_archivo_iniciar"),
    path("importaciones/<int:importacion_id>/archivos/<int:archivo_id>/completar/", CompletarArchivoImportadoView.as_view(), name="importacion_archivo_completar"),
    path("importaciones/<int:importacion_id>/analizar/", AnalizarImportacionView.as_view(), name="importacion_analizar"),
    path("importaciones/<int:pk>/", DetalleImportacionView.as_view(), name="importacion_detalle"),
    path("importaciones/<int:importacion_id>/registrar-paciente/", RegistrarPacienteDetectadoView.as_view(), name="importacion_registrar_paciente"),
    path("importaciones/<int:importacion_id>/confirmar/", ConfirmarImportacionView.as_view(), name="importacion_confirmar"),
    path("<int:pk>/", DetalleEstudioView.as_view(), name="estudio_detalle"),
]
