"""Configuración exclusiva del entorno local de desarrollo."""

from .base import *  # noqa: F403,F401

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", ".ngrok-free.app", ".ngrok-free.dev", ".ngrok.io", ".ngrok.app", "*"]

CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.app",
    "https://*.ngrok-free.dev",
    "https://*.ngrok.io",
    "https://*.ngrok.app",
]

# En desarrollo, los enlaces de recuperación se muestran en la terminal.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
