from django.contrib import admin
from django.urls import path, include

from apps.archivos.proxy_views import StorageProxyView

urlpatterns = [
    path("", include("apps.core.urls")),
    path("admin-django/", admin.site.urls),
    path("auth/", include("django.contrib.auth.urls")),
    path("pacientes/", include("apps.pacientes.urls")),
    path("estudios/", include("apps.estudios.urls")),
    path("archivos/", include("apps.archivos.urls")),
    path("storage-proxy/<path:s3_path>", StorageProxyView.as_view(), name="storage_proxy"),
    path("", include("apps.usuarios.urls")),
]


