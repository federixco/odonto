"""Configuración segura del entorno de producción."""

import os
from pathlib import PurePosixPath
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403,F401

DEBUG = False
# No permitir que el fallback local llegue accidentalmente al servidor real.
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("Producción requiere DJANGO_SECRET_KEY propia, aleatoria y de al menos 50 caracteres.")
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Producción requiere DJANGO_ALLOWED_HOSTS con dominios explícitos, sin comodín.")

# Este despliegue mantiene MySQL junto a Django: no admitir un destino remoto.
database = DATABASES["default"]
if database["ENGINE"] != "django.db.backends.mysql":
    raise ImproperlyConfigured("Producción requiere MySQL, no el fallback SQLite.")
for variable in ("DB_ENGINE", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SOCKET"):
    if not os.getenv(variable, "").strip():
        raise ImproperlyConfigured(f"Producción requiere configurar {variable}.")
if database["USER"].strip().lower() == "root":
    raise ImproperlyConfigured("Producción requiere una cuenta MySQL limitada, no root.")
socket = PurePosixPath(database["HOST"])
if not socket.is_absolute() or not socket.name or ".." in socket.parts or "\x00" in database["HOST"]:
    raise ImproperlyConfigured("DB_SOCKET debe ser una ruta Unix absoluta sin segmentos '..'.")

# None selecciona el endpoint HTTPS oficial de AWS; los endpoints personalizados
# (B2/R2/MinIO) deben ser HTTPS y no contener credenciales ni query strings.
if AWS_S3_ENDPOINT_URL:
    try:
        endpoint = urlsplit(AWS_S3_ENDPOINT_URL)
    except ValueError:
        raise ImproperlyConfigured("Producción requiere un endpoint S3 HTTPS válido.") from None
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username
            or endpoint.password or endpoint.query or endpoint.fragment):
        raise ImproperlyConfigured("Producción requiere un endpoint S3 HTTPS sin credenciales en la URL.")
for variable in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_STORAGE_BUCKET_NAME"):
    if not os.getenv(variable, "").strip():
        raise ImproperlyConfigured(f"Producción requiere configurar {variable}.")
for expiration in (AWS_S3_UPLOAD_EXPIRATION, AWS_S3_DOWNLOAD_EXPIRATION, AWS_S3_PREVIEW_EXPIRATION):
    if not 0 < expiration <= 604800:
        raise ImproperlyConfigured("Los vencimientos S3 deben estar entre 1 y 604800 segundos.")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "True").lower() == "true"
if not SECURE_SSL_REDIRECT:
    raise ImproperlyConfigured("Producción no permite desactivar la redirección a HTTPS.")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
