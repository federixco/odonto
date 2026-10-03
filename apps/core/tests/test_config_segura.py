"""Barreras de configuración, sin conexiones ni datos clínicos reales."""

import runpy
from unittest.mock import patch

from botocore.endpoint import Endpoint
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


class ConfiguracionSeguraTests(SimpleTestCase):
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
