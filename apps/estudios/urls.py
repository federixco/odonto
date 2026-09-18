from django.urls import path
from .views import (AgregarAccesoEstudioView, AnalizarImportacionView,
                    CompletarArchivoImportadoView, ConfirmarImportacionView, CrearEstudioView,
                    CrearImportacionView, DetalleEstudioView,
                    DetalleImportacionView, IniciarArchivoImportadoView,
                    EliminarEstudioView, IniciarImportacionView, ListaEstudiosView,
                    PurgarEstudioView,
                    RegistrarPacienteDetectadoView,
                    RevocarAccesoEstudioView, PublicarEstudioView, VerEstudioView)

urlpatterns = [
    path("", ListaEstudiosView.as_view(), name="estudio_lista"),
    path("crear/", CrearEstudioView.as_view(), name="estudio_crear"),
    path("<int:pk>/ver/", VerEstudioView.as_view(), name="estudio_ver"),
    path("importar/", CrearImportacionView.as_view(), name="importacion_crear"),
    path("importaciones/iniciar/", IniciarImportacionView.as_view(), name="importacion_iniciar"),
    path("importaciones/<int:importacion_id>/archivos/iniciar/", IniciarArchivoImportadoView.as_view(), name="importacion_archivo_iniciar"),
    path("importaciones/<int:importacion_id>/archivos/<int:archivo_id>/completar/", CompletarArchivoImportadoView.as_view(), name="importacion_archivo_completar"),
    path("importaciones/<int:importacion_id>/analizar/", AnalizarImportacionView.as_view(), name="importacion_analizar"),
    path("importaciones/<int:pk>/", DetalleImportacionView.as_view(), name="importacion_detalle"),
    path("importaciones/<int:importacion_id>/registrar-paciente/", RegistrarPacienteDetectadoView.as_view(), name="importacion_registrar_paciente"),
    path("importaciones/<int:importacion_id>/confirmar/", ConfirmarImportacionView.as_view(), name="importacion_confirmar"),
    path("<int:pk>/publicar/", PublicarEstudioView.as_view(), name="estudio_publicar"),
    path("<int:pk>/eliminar/", EliminarEstudioView.as_view(), name="estudio_eliminar"),
    path("<int:pk>/purgar/", PurgarEstudioView.as_view(), name="estudio_purgar"),
    path("<int:pk>/accesos/agregar/", AgregarAccesoEstudioView.as_view(), name="estudio_acceso_agregar"),
    path("<int:pk>/accesos/<int:autorizacion_id>/revocar/", RevocarAccesoEstudioView.as_view(), name="estudio_acceso_revocar"),
    path("<int:pk>/", DetalleEstudioView.as_view(), name="estudio_detalle"),
]
