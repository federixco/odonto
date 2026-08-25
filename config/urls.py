"""Enrutador principal. Cada módulo deberá declarar sus propias URL."""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin-django/", admin.site.urls),
]

