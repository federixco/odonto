"""Fecha de la política e inventario interno de cookies; no modifica la sesión."""

from datetime import date

from django.conf import settings
from django.contrib.messages.storage.cookie import CookieStorage


PRIVACY_LAST_UPDATED = date(2026, 10, 16)


def _duration(seconds):
    days = seconds / 86400
    if days >= 1:
        return f"Hasta {days:g} días" + (" (aproximadamente un año)" if days >= 360 else "")
    return f"Hasta {seconds / 3600:g} horas"


def application_cookies():
    """Solo cookies de la instalación actual; no enumera servicios hipotéticos."""
    cookies = [{
        "name": settings.SESSION_COOKIE_NAME,
        "purpose": "Identifica la sesión y permite mantener el acceso a la cuenta. El identificador remite a la sesión almacenada por el sistema.",
        "duration": (
            "Durante la sesión del navegador; al cerrarlo puede eliminarse."
            if settings.SESSION_EXPIRE_AT_BROWSER_CLOSE
            else _duration(settings.SESSION_COOKIE_AGE) + ". Puede renovarse al modificarse la sesión; se elimina al cerrar sesión."
        ),
        "blocked": "No se puede mantener la sesión iniciada ni utilizar normalmente las funciones que requieren autenticación.",
    }]
    if not settings.CSRF_USE_SESSIONS:
        cookies.append({
            "name": settings.CSRF_COOKIE_NAME,
            "purpose": "Permite comprobar el origen de las solicitudes que modifican información y protege los formularios contra solicitudes falsificadas (CSRF).",
            "duration": _duration(settings.CSRF_COOKIE_AGE) + ". Puede renovarse al utilizar formularios.",
            "blocked": "Los formularios protegidos, incluido el inicio de sesión, pueden rechazarse por no poder verificar la solicitud.",
        })
    if settings.MESSAGE_STORAGE in {
        "django.contrib.messages.storage.cookie.CookieStorage",
        "django.contrib.messages.storage.fallback.FallbackStorage",
    }:
        cookies.append({
            "name": CookieStorage.cookie_name,
            "purpose": "Transporta avisos temporales de resultado o error entre páginas. Solo aparece cuando hay mensajes que guardar; si no caben, la configuración actual puede usar la sesión.",
            "duration": "Cookie de sesión, sin fecha persistente de caducidad. Se retira al consumir los mensajes o al cerrar el navegador; la restauración de sesiones del navegador puede conservarla.",
            "blocked": "Algunos avisos de confirmación o error pueden no mostrarse después de una redirección.",
        })
    return cookies
