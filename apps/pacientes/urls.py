from django.urls import path

from . import views


urlpatterns = [
    path("", views.ListaPacientesView.as_view(), name="paciente_lista"),
    path("crear/", views.CrearPacienteView.as_view(), name="paciente_crear"),
    path("<int:pk>/", views.DetallePacienteView.as_view(), name="paciente_detalle"),
    path("<int:pk>/editar/", views.EditarPacienteView.as_view(), name="paciente_editar"),
    path("<int:pk>/crear-acceso/", views.CrearAccesoPacienteView.as_view(), name="paciente_acceso_crear"),
]
