"""Proxy local para desarrollo: reenvía peticiones directas de almacenamiento hacia MinIO.

Permite que navegadores que acceden por HTTPS (ej. ngrok) o desde dispositivos remotos
puedan cargar y descargar archivos sin ser bloqueados por Mixed Content o CORS.
La firma AWS SigV4 se valida correctamente porque el proxy preserva la cabecera Host original.
"""

import http.client
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt


@method_decorator(csrf_exempt, name="dispatch")
class StorageProxyView(View):
    """Reenvía peticiones S3/MinIO para desarrollo."""

    def options(self, request, s3_path=""):
        response = HttpResponse()
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, PUT, HEAD, OPTIONS"
        response["Access-Control-Allow-Headers"] = "*"
        response["Access-Control-Expose-Headers"] = "ETag, Content-Length, Content-Type, Content-Range"
        response["Access-Control-Max-Age"] = "86400"
        return response

    def _get_target_conn(self):
        endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", None) or "http://127.0.0.1:9020"
        parsed = urlparse(endpoint)
        is_https = parsed.scheme == "https"
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if is_https else 80)
        if is_https:
            conn = http.client.HTTPSConnection(host, port, timeout=120)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=120)
        return conn, parsed.netloc

    def put(self, request, s3_path=""):
        conn, netloc = self._get_target_conn()
        query = request.META.get("QUERY_STRING", "")
        target_path = f"/{s3_path.lstrip('/')}"
        if query:
            target_path += f"?{query}"

        headers = {
            "Host": netloc,
        }
        if "CONTENT_TYPE" in request.META:
            headers["Content-Type"] = request.META["CONTENT_TYPE"]
        elif "Content-Type" in request.headers:
            headers["Content-Type"] = request.headers["Content-Type"]

        body_data = request.body
        headers["Content-Length"] = str(len(body_data))

        try:
            conn.request("PUT", target_path, body=body_data, headers=headers)
            resp = conn.getresponse()
            content = resp.read()
            response = HttpResponse(content, status=resp.status)
            etag = resp.getheader("ETag")
            if etag:
                response["ETag"] = etag
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Expose-Headers"] = "ETag, Content-Length, Content-Type, Content-Range"
            return response
        finally:
            conn.close()

    def get(self, request, s3_path=""):
        conn, netloc = self._get_target_conn()
        query = request.META.get("QUERY_STRING", "")
        target_path = f"/{s3_path.lstrip('/')}"
        if query:
            target_path += f"?{query}"

        headers = {
            "Host": netloc,
        }
        if "HTTP_RANGE" in request.META:
            headers["Range"] = request.META["HTTP_RANGE"]

        try:
            conn.request("GET", target_path, headers=headers)
            resp = conn.getresponse()

            def stream_content():
                try:
                    while chunk := resp.read(64 * 1024):
                        yield chunk
                finally:
                    conn.close()

            response = StreamingHttpResponse(stream_content(), status=resp.status)
            for header in ["Content-Type", "Content-Length", "Content-Range", "Content-Disposition", "ETag", "Accept-Ranges"]:
                val = resp.getheader(header)
                if val:
                    response[header] = val
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Expose-Headers"] = "ETag, Content-Length, Content-Type, Content-Range"
            return response
        except Exception:
            conn.close()
            raise

    def head(self, request, s3_path=""):
        conn, netloc = self._get_target_conn()
        query = request.META.get("QUERY_STRING", "")
        target_path = f"/{s3_path.lstrip('/')}"
        if query:
            target_path += f"?{query}"

        headers = {
            "Host": netloc,
        }
        try:
            conn.request("HEAD", target_path, headers=headers)
            resp = conn.getresponse()
            response = HttpResponse(status=resp.status)
            for header in ["Content-Type", "Content-Length", "Content-Range", "Content-Disposition", "ETag", "Accept-Ranges"]:
                val = resp.getheader(header)
                if val:
                    response[header] = val
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Expose-Headers"] = "ETag, Content-Length, Content-Type, Content-Range"
            return response
        finally:
            conn.close()
