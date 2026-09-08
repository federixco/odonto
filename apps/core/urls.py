"""Rutas públicas de la institución, separadas de las funciones de usuarios."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [path("", views.landing, name="landing")]
