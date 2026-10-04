"""Configuración aislada para pruebas automatizadas."""

from .base import *  # noqa: F403,F401

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CARGA_LOG_ENABLED = False
TEST_RUNNER = "apps.core.test_runner.RunnerSinStorageReal"
# No heredar buckets/credenciales de .env. El runner bloquea además el I/O.
AWS_ACCESS_KEY_ID = "test-only"
AWS_SECRET_ACCESS_KEY = "test-only"
AWS_STORAGE_BUCKET_NAME = "unit-tests-no-real-storage"
AWS_S3_ENDPOINT_URL = "http://127.0.0.1:9"
