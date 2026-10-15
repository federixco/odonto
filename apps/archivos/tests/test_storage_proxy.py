"""Pruebas unitarias para StorageProxyView."""

from unittest.mock import Mock, patch
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.archivos.proxy_views import StorageProxyView


@override_settings(AWS_S3_ENDPOINT_URL="http://127.0.0.1:9020")
class StorageProxyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = StorageProxyView.as_view()

    def test_options_retorna_cabeceras_cors(self):
        request = self.factory.options("/storage-proxy/test-bucket/archivo.dcm")
        response = self.view(request, s3_path="test-bucket/archivo.dcm")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")
        self.assertIn("PUT", response["Access-Control-Allow-Methods"])
        self.assertIn("ETag", response["Access-Control-Expose-Headers"])

    @patch("http.client.HTTPConnection")
    def test_put_reenvia_cuerpo_y_devuelve_etag(self, mock_conn_cls):
        mock_conn = Mock()
        mock_resp = Mock()
        mock_resp.status = 200
        mock_resp.getheader.side_effect = lambda h: '"etag-12345"' if h.lower() == "etag" else None
        mock_resp.read.return_value = b""
        mock_conn.getresponse.return_value = mock_resp
        mock_conn_cls.return_value = mock_conn

        request = self.factory.put(
            "/storage-proxy/test-bucket/archivo.dcm?uploadId=123&partNumber=1",
            data=b"chunk data",
            content_type="application/octet-stream",
        )
        response = self.view(request, s3_path="test-bucket/archivo.dcm")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["ETag"], '"etag-12345"')
        mock_conn.request.assert_called_once()
        args, kwargs = mock_conn.request.call_args
        self.assertEqual(args[0], "PUT")
        self.assertTrue(args[1].startswith("/test-bucket/archivo.dcm?uploadId=123"))
        self.assertEqual(kwargs["body"], b"chunk data")
        self.assertEqual(kwargs["headers"]["Host"], "127.0.0.1:9020")
