"""Exclusión por recurso, sin mantener una transacción abierta durante I/O S3."""
from contextlib import contextmanager
from functools import wraps
import hashlib

from django.db import connection
from django.http import JsonResponse


class RecursoOcupado(Exception):
    pass


@contextmanager
def bloquear_recurso(recurso):
    if connection.vendor != "mysql":
        raise RuntimeError("Los bloqueos de transferencias requieren MySQL.")
    nombre = "doc:" + hashlib.sha256(
        f"{connection.settings_dict['NAME']}:{recurso}".encode()
    ).hexdigest()[:60]
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 0)", [nombre])
        if cursor.fetchone()[0] != 1:
            raise RecursoOcupado()
    def comprobar():
        with connection.cursor() as cursor:
            cursor.execute("SELECT IS_USED_LOCK(%s) = CONNECTION_ID()", [nombre])
            if cursor.fetchone()[0] != 1:
                raise RecursoOcupado()
    try:
        yield comprobar
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [nombre])


def transferencia_exclusiva(clave):
    def decorador(funcion):
        @wraps(funcion)
        def ejecutar(self, request, *args, **kwargs):
            try:
                with bloquear_recurso(clave(request, **kwargs)) as comprobar:
                    request.comprobar_bloqueo_transferencia = comprobar
                    return funcion(self, request, *args, **kwargs)
            except RecursoOcupado:
                respuesta = JsonResponse({"error": "Operación en curso. Reintentá en unos segundos.", "reintentable": True}, status=409)
                respuesta["Retry-After"] = "2"
                return respuesta
        return ejecutar
    return decorador
