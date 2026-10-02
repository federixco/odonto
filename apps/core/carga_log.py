"""Diagnóstico temporal de cargas: solo identificadores y datos técnicos."""

import json
import logging
from pathlib import PurePath
import traceback

from django.conf import settings


logger = logging.getLogger("doc.cargas")


def registrar_carga(etapa, *, importacion_id=None, archivo_id=None,
                    estudio_id=None, cantidad=None, bytes_total=None,
                    partes=None, duracion_ms=None, error=None):
    """Nunca serializa archivos, pacientes, URLs ni mensajes de excepciones.

    Los mensajes de boto3/pydicom pueden contener rutas, URLs o datos clínicos.
    Conservamos únicamente el tipo de excepción y su ubicación en el código.
    """
    if not getattr(settings, "CARGA_LOG_ENABLED", False):
        return
    datos = {"etapa": etapa}
    for nombre, valor in {
        "importacion_id": importacion_id, "archivo_id": archivo_id,
        "estudio_id": estudio_id, "cantidad": cantidad,
        "bytes_total": bytes_total, "partes": partes, "duracion_ms": duracion_ms,
    }.items():
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            datos[nombre] = valor
    if error is not None:
        datos["error_tipo"] = type(error).__name__
        datos["ubicaciones"] = [
            {"modulo": PurePath(frame.filename).name,
             "funcion": frame.name, "linea": frame.lineno}
            for frame in traceback.extract_tb(error.__traceback__)[-8:]
        ]
    logger.log(logging.WARNING if error is not None else logging.INFO,
               json.dumps(datos, ensure_ascii=True))
