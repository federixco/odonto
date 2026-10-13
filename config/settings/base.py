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


def _env_int(name, default):
    """Lee un entero positivo desde el entorno y falla con un mensaje claro."""

    value = int(os.getenv(name, default))
    if value <= 0:
        raise ValueError(f"{name} debe ser un entero positivo.")
    return value


def _database_name(engine):
    """Resuelve rutas relativas de SQLite y conserva nombres de MySQL."""

    default = str(BASE_DIR / "db.sqlite3") if engine.endswith("sqlite3") else "sisetma"
    name = os.getenv("DB_NAME", default)
    if engine.endswith("sqlite3") and name != ":memory:":
        path = Path(name)
        return str(path if path.is_absolute() else BASE_DIR / path)
    return name


def _database_connection(engine):
    """Usa TCP en desarrollo o un socket Unix explícito en el VPS Linux."""
    socket = os.getenv("DB_SOCKET", "").strip()
    return {
        "ENGINE": engine,
        "NAME": _database_name(engine),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": socket if socket and engine == "django.db.backends.mysql" else os.getenv("DB_HOST", ""),
        "PORT": "" if socket and engine == "django.db.backends.mysql" else os.getenv("DB_PORT", ""),
    }


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

DATABASES = {"default": _database_connection(DB_ENGINE)}

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

# --- Autenticación y correos (Etapa 2) ---
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "redireccion_roles"
LOGOUT_REDIRECT_URL = "login"
PASSWORD_RESET_TIMEOUT = 60 * 60


# --- Almacenamiento privado S3 / MinIO (Etapa 3) ---
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "sisetma-estudios")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL") or None
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "path")
AWS_S3_PRESIGNED_EXPIRATION = _env_int("AWS_S3_PRESIGNED_EXPIRATION", 3600)
# La variable histórica solo sirve de fallback para subidas, no para lecturas.
AWS_S3_UPLOAD_EXPIRATION = _env_int("AWS_S3_UPLOAD_EXPIRATION", AWS_S3_PRESIGNED_EXPIRATION)
AWS_S3_DOWNLOAD_EXPIRATION = _env_int("AWS_S3_DOWNLOAD_EXPIRATION", 300)
AWS_S3_PREVIEW_EXPIRATION = _env_int("AWS_S3_PREVIEW_EXPIRATION", 900)
S3_MULTIPART_PART_SIZE = _env_int("S3_MULTIPART_PART_SIZE", 10 * 1024 * 1024)
S3_MAX_UPLOAD_SIZE = _env_int("S3_MAX_UPLOAD_SIZE", 2 * 1024 * 1024 * 1024)
S3_HASH_CHUNK_SIZE = _env_int("S3_HASH_CHUNK_SIZE", 8 * 1024 * 1024)
# Límite lógico para una importación de carpeta, independiente del máximo por archivo.
IMPORTACION_MAX_ARCHIVOS = _env_int("IMPORTACION_MAX_ARCHIVOS", 5000)
IMPORTACION_MAX_TAMANO_TOTAL = _env_int("IMPORTACION_MAX_TAMANO_TOTAL", 10 * 1024 * 1024 * 1024)

# ZIP: I/O acotado, una preparación simultánea y capacidad temporal explícita.
ZIP_MAX_TAMANO_TOTAL = _env_int("ZIP_MAX_TAMANO_TOTAL", 10 * 1024 * 1024 * 1024)
ZIP_MAX_ARCHIVOS = _env_int("ZIP_MAX_ARCHIVOS", 5000)
ZIP_RESERVA_DISCO = _env_int("ZIP_RESERVA_DISCO", 512 * 1024 * 1024)
ZIP_TEMP_DIR = os.getenv("ZIP_TEMP_DIR") or None

# Visor: caché técnica privada (nunca MEDIA/STATIC), compartida con el worker.
VISOR_CACHE_DIR = BASE_DIR / "data" / "visor"
VISOR_CACHE_TTL = _env_int("VISOR_CACHE_TTL", 3600)
VISOR_HEADER_BYTES = _env_int("VISOR_HEADER_BYTES", 512 * 1024)
VISOR_MAX_FILES = _env_int("VISOR_MAX_FILES", 5000)
VISOR_MAX_MESH_BYTES = _env_int("VISOR_MAX_MESH_BYTES", 80 * 1024 * 1024)
VISOR_MAX_VERTICES = _env_int("VISOR_MAX_VERTICES", 2000000)
VISOR_MAX_FRAMES = _env_int("VISOR_MAX_FRAMES", 1500)
VISOR_MAX_IMAGE_BYTES = _env_int("VISOR_MAX_IMAGE_BYTES", 64 * 1024 * 1024)
VISOR_MAX_VOLUME_BYTES = _env_int("VISOR_MAX_VOLUME_BYTES", 256 * 1024 * 1024)
VISOR_CONCURRENCY = max(1, min(4, _env_int("VISOR_CONCURRENCY", 4)))

# Diagnóstico opt-in de pruebas: 5 MiB por archivo y tres copias anteriores.
CARGA_LOG_ENABLED = _env_bool("CARGA_LOG_ENABLED", False)
if CARGA_LOG_ENABLED:
    (BASE_DIR / "logs").mkdir(exist_ok=True)
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"cargas": {"format": "{asctime} {levelname} {message}", "style": "{"}},
        "handlers": {
            "cargas": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(BASE_DIR / "logs" / "cargas.log"),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 3,
                "encoding": "utf-8",
                "delay": True,
                "formatter": "cargas",
                "level": "INFO",
            },
        },
        "loggers": {"doc.cargas": {"handlers": ["cargas"], "level": "INFO", "propagate": False}},
    }

