"""Configuración compartida por todos los entornos."""

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=False)


def _env_bool(name, default=False):
    """Lee un booleano desde el entorno sin reemplazar valores ya exportados."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_name(engine):
    """Resuelve rutas relativas de SQLite y conserva nombres de MySQL."""

    default = str(BASE_DIR / "db.sqlite3") if engine.endswith("sqlite3") else "sisetma"
    name = os.getenv("DB_NAME", default)
    if engine.endswith("sqlite3") and name != ":memory:":
        path = Path(name)
        return str(path if path.is_absolute() else BASE_DIR / path)
    return name


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = _env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core.apps.CoreConfig",
    "apps.usuarios.apps.UsuariosConfig",
    "apps.pacientes.apps.PacientesConfig",
    "apps.estudios.apps.EstudiosConfig",
    "apps.archivos.apps.ArchivosConfig",
    "apps.accesos.apps.AccesosConfig",
    "apps.auditoria.apps.AuditoriaConfig",
    "apps.notificaciones.apps.NotificacionesConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")

DATABASES = {"default": {
    "ENGINE": DB_ENGINE,
    "NAME": _database_name(DB_ENGINE),
    "USER": os.getenv("DB_USER", ""),
    "PASSWORD": os.getenv("DB_PASSWORD", ""),
    "HOST": os.getenv("DB_HOST", ""),
    "PORT": os.getenv("DB_PORT", ""),
}}

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "usuarios.Usuario"
SESSION_COOKIE_HTTPONLY = True

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# --- Autenticación y Correos (Etapa 2) ---
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "redireccion_roles"
LOGOUT_REDIRECT_URL = "login"
PASSWORD_RESET_TIMEOUT = 60 * 60
