from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("", include("apps.core.urls")),
    path("admin-django/", admin.site.urls),
    path("auth/", include("django.contrib.auth.urls")),
    path("", include("apps.usuarios.urls")),
]


