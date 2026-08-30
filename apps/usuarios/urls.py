from django.urls import path

from . import views

urlpatterns = [
    path("inicio/", views.redireccion_roles_view, name="redireccion_roles"),
    path("admin-centro/", views.DashboardAdminView.as_view(), name="dashboard_admin"),
    path("mi-consultorio/", views.DashboardOdontologoView.as_view(), name="dashboard_odontologo"),
    path("mis-estudios/", views.DashboardPacienteView.as_view(), name="dashboard_paciente"),
]
