"""Configuración exclusiva del entorno local de desarrollo."""

from .base import *  # noqa: F403,F401

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# En desarrollo, los enlaces de recuperación se muestran en la terminal.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
