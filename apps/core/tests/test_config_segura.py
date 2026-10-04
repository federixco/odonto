"""Barreras de configuración, sin conexiones ni datos clínicos reales."""

import runpy
from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import patch

from botocore.endpoint import Endpoint
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.settings.base import _database_connection


class ConfiguracionSeguraTests(SimpleTestCase):
    def produccion(self, *, database=None, endpoint="https://storage.example.test", **env):
        """Carga producción con valores ficticios, sin conectar a ningún servicio."""
        variables = {
            "DJANGO_ALLOWED_HOSTS": "doc.example.test",
            "DB_ENGINE": "django.db.backends.mysql", "DB_NAME": "prueba",
            "DB_USER": "doc_app", "DB_PASSWORD": "clave-ficticia",
            "DB_SOCKET": "/run/mysqld/mysqld.sock",
            "AWS_ACCESS_KEY_ID": "clave-ficticia", "AWS_SECRET_ACCESS_KEY": "secreto-ficticio",
            "AWS_STORAGE_BUCKET_NAME": "bucket-ficticio",
        }
        variables.update(env)
        conexion = database or {
            "ENGINE": "django.db.backends.mysql", "NAME": "prueba", "USER": "doc_app",
            "PASSWORD": "clave-ficticia", "HOST": "/run/mysqld/mysqld.sock", "PORT": "",
        }
        with ExitStack() as patches:
            patches.enter_context(patch.dict("os.environ", variables, clear=True))
            patches.enter_context(patch("config.settings.base.SECRET_KEY", "solo-ficticia-para-tests-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
            patches.enter_context(patch("config.settings.base.DATABASES", {"default": deepcopy(conexion)}))
            patches.enter_context(patch("config.settings.base.AWS_S3_ENDPOINT_URL", endpoint))
            return runpy.run_module("config.settings.production")

    def test_produccion_acepta_socket_y_s3_https(self):
        resultado = self.produccion()
        self.assertFalse(resultado["DEBUG"])
        self.assertTrue(resultado["SECURE_SSL_REDIRECT"])
        self.assertTrue(resultado["SESSION_COOKIE_SECURE"])

    def test_produccion_acepta_endpoint_https_por_defecto_de_aws(self):
        self.produccion(endpoint=None)

    def test_produccion_rechaza_sqlite(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "MySQL"):
            self.produccion(database={"ENGINE": "django.db.backends.sqlite3"})

    def test_produccion_rechaza_root(self):
        conexion = {"ENGINE": "django.db.backends.mysql", "USER": "ROOT"}
        with self.assertRaisesRegex(ImproperlyConfigured, "no root"):
            self.produccion(database=conexion, DB_USER="ROOT")

    def test_produccion_rechaza_variables_vacias(self):
        for variable in ("DB_ENGINE", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SOCKET",
                         "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_STORAGE_BUCKET_NAME"):
            with self.subTest(variable=variable):
                with self.assertRaisesRegex(ImproperlyConfigured, variable):
                    self.produccion(**{variable: " "})

    def test_produccion_rechaza_socket_no_local(self):
        for host in ("/", "127.0.0.1", "mysql.example.test", "run/mysql.sock", "/run/../mysql.sock", "/run/\x00mysql.sock"):
            conexion = {"ENGINE": "django.db.backends.mysql", "USER": "doc_app", "HOST": host}
            with self.subTest(host=host), self.assertRaisesRegex(ImproperlyConfigured, "DB_SOCKET"):
                self.produccion(database=conexion)

    def test_produccion_rechaza_s3_http_y_urls_con_secretos(self):
        for url in ("https://[invalid-secret", "http://storage.example.test", "https://", "https://user:secret@storage.example.test",
                    "https://storage.example.test?token=secret", "https://storage.example.test#secret"):
            with self.subTest(url=url), self.assertRaisesRegex(ImproperlyConfigured, "HTTPS") as error:
                self.produccion(endpoint=url)
            self.assertNotIn("secret", str(error.exception))

    def test_produccion_rechaza_redireccion_https_desactivada(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "redirección"):
            self.produccion(DJANGO_SECURE_SSL_REDIRECT="False")

    def test_produccion_limita_vencimientos_s3(self):
        for nombre in ("AWS_S3_UPLOAD_EXPIRATION", "AWS_S3_DOWNLOAD_EXPIRATION", "AWS_S3_PREVIEW_EXPIRATION"):
            with patch("config.settings.base." + nombre, 604801):
                with self.assertRaisesRegex(ImproperlyConfigured, "vencimientos"):
                    self.produccion()

    def test_socket_tiene_prioridad_sobre_tcp(self):
        with patch.dict("os.environ", {"DB_SOCKET": "/run/mysql.sock", "DB_HOST": "127.0.0.1", "DB_PORT": "3306"}):
            conexion = _database_connection("django.db.backends.mysql")
        self.assertEqual(conexion["HOST"], "/run/mysql.sock")
        self.assertEqual(conexion["PORT"], "")

    def test_desarrollo_conserva_tcp_sin_socket(self):
        with patch.dict("os.environ", {"DB_SOCKET": "", "DB_HOST": "127.0.0.1", "DB_PORT": "3306"}):
            conexion = _database_connection("django.db.backends.mysql")
        self.assertEqual(conexion["HOST"], "127.0.0.1")
        self.assertEqual(conexion["PORT"], "3306")

    def test_sqlite_no_utiliza_el_socket_mysql(self):
        with patch.dict("os.environ", {"DB_SOCKET": "/run/mysql.sock", "DB_HOST": ""}):
            self.assertEqual(_database_connection("django.db.backends.sqlite3")["HOST"], "")

    def test_suite_bloquea_transporte_s3(self):
        # Endpoint.make_request debe estar sustituido por nuestro test runner.
        with self.assertRaisesRegex(AssertionError, "no admite S3 real"):
            Endpoint.make_request(None, None, {})

    @patch("config.settings.base.SECRET_KEY", "dev-only-change-me")
    def test_produccion_rechaza_clave_de_desarrollo(self):
        with self.assertRaises(ImproperlyConfigured):
            runpy.run_module("config.settings.production")

    @patch("config.settings.base.SECRET_KEY", "solo-ficticia-para-tests-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    @patch.dict("os.environ", {"DJANGO_ALLOWED_HOSTS": "*"})
    def test_produccion_rechaza_hosts_comodin(self):
        with self.assertRaises(ImproperlyConfigured):
            runpy.run_module("config.settings.production")
