from django.urls import path

from . import views

urlpatterns = [
    # Redirección post-login
    path("inicio/", views.redireccion_roles_view, name="redireccion_roles"),

    # Dashboards
    path("admin-centro/", views.DashboardAdminView.as_view(), name="dashboard_admin"),
    path("mi-consultorio/", views.DashboardOdontologoView.as_view(), name="dashboard_odontologo"),
    path("mis-estudios/", views.DashboardPacienteView.as_view(), name="dashboard_paciente"),

    # Gestión de odontólogos (Admin)
    path("odontologos/", views.ListaOdontologosView.as_view(), name="odontologo_lista"),
    path("odontologos/crear/", views.CrearOdontologoView.as_view(), name="odontologo_crear"),
    path("odontologos/<int:pk>/", views.DetalleOdontologoView.as_view(), name="odontologo_detalle"),
    path("odontologos/<int:pk>/editar/", views.EditarOdontologoView.as_view(), name="odontologo_editar"),
    path("odontologos/<int:pk>/habilitar/", views.HabilitarOdontologoView.as_view(), name="odontologo_habilitar"),
    path("odontologos/<int:pk>/deshabilitar/", views.DeshabilitarOdontologoView.as_view(), name="odontologo_deshabilitar"),

    # Autorregistro público
    path("registro-odontologo/", views.AutoregistroOdontologoView.as_view(), name="odontologo_autoregistro"),
]
