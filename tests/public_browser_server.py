"""Páginas públicas reales para Playwright, solo loopback y sin consultas a BD.

No inicia la aplicación clínica ni modifica MySQL/MinIO. La configuración
describe MySQL; las vistas públicas y formularios GET no necesitan conectarse.
"""
import os
import secrets
import threading
from wsgiref.simple_server import make_server, WSGIRequestHandler

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test_mysql"

from django.core.wsgi import get_wsgi_application
from django.contrib.staticfiles.handlers import StaticFilesHandler


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


if __name__ == "__main__":
    django_application = StaticFilesHandler(get_wsgi_application())

    def application(environ, start_response):
        if environ.get("PATH_INFO") == "/__test_shutdown" and environ.get("REQUEST_METHOD") == "POST":
            token = os.environ.get("DOC_PUBLIC_TEST_TOKEN", "")
            if token and secrets.compare_digest(token, environ.get("HTTP_X_TEST_TOKEN", "")):
                start_response("200 OK", [("Content-Type", "text/plain")])
                threading.Thread(target=server.shutdown, daemon=True).start()
                return [b"closing"]
            start_response("403 Forbidden", [("Content-Type", "text/plain")])
            return [b"forbidden"]
        return django_application(environ, start_response)

    with make_server("127.0.0.1", 8767, application, handler_class=QuietHandler) as server:
        print("Páginas públicas de prueba: http://127.0.0.1:8767/", flush=True)
        server.serve_forever()
