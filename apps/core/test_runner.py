"""Suite unitaria: nunca permite transporte hacia S3 real, ni siquiera local."""

from unittest.mock import patch

from django.test.runner import DiscoverRunner


class RunnerSinStorageReal(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._storage = patch(
            "botocore.endpoint.Endpoint.make_request",
            side_effect=AssertionError(
                "La suite unitaria no admite S3 real: simulá la operación de storage."
            ),
        )
        self._storage.start()

    def teardown_test_environment(self, **kwargs):
        try:
            self._storage.stop()
        finally:
            super().teardown_test_environment(**kwargs)
