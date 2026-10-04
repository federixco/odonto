"""Pruebas aisladas con MySQL; nunca usar la base real ni SQLite."""

from copy import deepcopy
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured

from .test import *  # noqa: F403,F401
from .base import DATABASES as DATABASES_BASE

DATABASES = deepcopy(DATABASES_BASE)
if DATABASES["default"]["ENGINE"] != "django.db.backends.mysql":
    raise ImproperlyConfigured("Estas pruebas requieren MySQL configurado.")

# Un nombre independiente por ejecución evita conflictos con pruebas paralelas.
# Django crea la base de prueba y la destruye al finalizar; no modifica la base
# configurada en .env. El usuario MySQL necesita permisos para crearla.
DATABASES["default"]["TEST"] = {
    "NAME": f"test_odonto_revision_{uuid4().hex[:8]}",
    "CHARSET": "utf8mb4",
}
