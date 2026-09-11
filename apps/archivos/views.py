"""Endpoints autenticados para coordinar cargas directas a S3/MinIO."""

import json
import logging
import math
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from apps.auditoria.models import LogActividad
from apps.core.enums import (
    CategoriaArchivo,
    EstadoArchivo,
    EstadoEstudio,
    FormatoArchivo,
    TipoEvento,
)
from apps.core.mixins import AdminRequeridoMixin
from apps.estudios.models import Estudio

from .models import Archivo
from .services.storage import (
    abortar_multipart_upload,
    calcular_sha256_objeto,
    completar_multipart_upload,
    eliminar_objeto,
    generar_urls_prefirmadas,
    iniciar_multipart_upload,
)


logger = logging.getLogger(__name__)
S3_MIN_PART_SIZE = 5 * 1024 * 1024
S3_MAX_PARTS = 10_000

FORMATOS_PERMITIDOS = {
    ".dcm": (FormatoArchivo.DICOM, CategoriaArchivo.DICOM, "application/dicom"),
    ".dicom": (FormatoArchivo.DICOM, CategoriaArchivo.DICOM, "application/dicom"),
    ".stl": (FormatoArchivo.STL, CategoriaArchivo.MODELO_3D, "model/stl"),
    ".ply": (FormatoArchivo.PLY, CategoriaArchivo.MODELO_3D, "application/octet-stream"),
    ".jpg": (FormatoArchivo.JPG, CategoriaArchivo.IMAGEN_DOCUMENTO, "image/jpeg"),
    ".jpeg": (FormatoArchivo.JPG, CategoriaArchivo.IMAGEN_DOCUMENTO, "image/jpeg"),
    ".png": (FormatoArchivo.PNG, CategoriaArchivo.IMAGEN_DOCUMENTO, "image/png"),
    ".tif": (FormatoArchivo.TIFF, CategoriaArchivo.IMAGEN_DOCUMENTO, "image/tiff"),
    ".tiff": (FormatoArchivo.TIFF, CategoriaArchivo.IMAGEN_DOCUMENTO, "image/tiff"),
    ".pdf": (FormatoArchivo.PDF, CategoriaArchivo.IMAGEN_DOCUMENTO, "application/pdf"),
}


def _leer_json(request):
    try:
        data = json.loads(request.body)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _clasificar_nombre(nombre):
    """Valida el nombre visible y deriva formato/categoría en el servidor."""

    if not isinstance(nombre, str):
        return None
    nombre = nombre.strip()
    if (
        not nombre
        or len(nombre) > 255
        or Path(nombre).name != nombre
        or "\\" in nombre
        or any(ord(caracter) < 32 for caracter in nombre)
    ):
        return None
    extension = Path(nombre).suffix.lower()
    clasificacion = FORMATOS_PERMITIDOS.get(extension)
    if clasificacion is None:
        return None
    return nombre, extension, *clasificacion


def _normalizar_partes(partes, cantidad_esperada):
    """Evita completar uploads con partes repetidas, faltantes o manipuladas."""

    if not isinstance(partes, list) or len(partes) != cantidad_esperada:
        return None
    normalizadas = []
    for parte in partes:
        if not isinstance(parte, dict):
            return None
        numero = parte.get("PartNumber")
        etag = parte.get("ETag")
        if (
            isinstance(numero, bool)
            or not isinstance(numero, int)
            or not isinstance(etag, str)
            or not etag
            or len(etag) > 1024
        ):
            return None
        normalizadas.append({"PartNumber": numero, "ETag": etag})
    normalizadas.sort(key=lambda parte: parte["PartNumber"])
    if [parte["PartNumber"] for parte in normalizadas] != list(
        range(1, cantidad_esperada + 1)
    ):
        return None
    return normalizadas


class IniciarArchivoView(AdminRequeridoMixin, View):
    """Crea el registro transitorio y entrega permisos de subida temporales."""

    def post(self, request, estudio_id):
        estudio = get_object_or_404(Estudio, pk=estudio_id)
        if estudio.estado not in {EstadoEstudio.BORRADOR, EstadoEstudio.EN_REVISION}:
            return JsonResponse(
                {"error": "Solo se pueden cargar archivos en estudios editables."},
                status=409,
            )

        data = _leer_json(request)
        clasificacion = _clasificar_nombre(data.get("nombre_archivo") if data else None)
        try:
            tamano = int(data.get("tamano", 0)) if data else 0
        except (TypeError, ValueError):
            tamano = 0

        if clasificacion is None:
            return JsonResponse(
                {"error": "El nombre o el formato del archivo no está permitido."},
                status=400,
            )
        if tamano <= 0 or tamano > settings.S3_MAX_UPLOAD_SIZE:
            return JsonResponse(
                {"error": "El tamaño del archivo está vacío o supera el límite permitido."},
                status=400,
            )
        if settings.S3_MULTIPART_PART_SIZE < S3_MIN_PART_SIZE:
            logger.error("S3_MULTIPART_PART_SIZE es menor que el mínimo de S3.")
            return JsonResponse({"error": "Configuración de carga inválida."}, status=500)

        nombre, extension, formato, categoria, content_type = clasificacion
        cantidad_partes = math.ceil(tamano / settings.S3_MULTIPART_PART_SIZE)
        if cantidad_partes > S3_MAX_PARTS:
            return JsonResponse({"error": "El archivo requiere demasiadas partes."}, status=400)

        clave_objeto = (
            f"estudios/{estudio.pk}/archivos/{uuid.uuid4().hex}{extension}"
        )
        upload_id = None
        archivo = None
        try:
            upload_id = iniciar_multipart_upload(clave_objeto, content_type)
            archivo = Archivo.objects.create(
                estudio=estudio,
                nombre_archivo=nombre,
                formato=formato,
                categoria=categoria,
                ruta_almacenamiento=clave_objeto,
                tamano=tamano,
                upload_id=upload_id,
                content_type=content_type,
                cantidad_partes=cantidad_partes,
                estado=EstadoArchivo.CARGANDO,
            )
            urls = generar_urls_prefirmadas(
                clave_objeto,
                upload_id,
                cantidad_partes,
            )
        except Exception:
            logger.exception("No se pudo iniciar la carga multipartes.")
            if upload_id:
                abortar_multipart_upload(clave_objeto, upload_id)
            if archivo:
                Archivo.objects.filter(pk=archivo.pk).update(
                    estado=EstadoArchivo.INCORRECTO,
                    upload_id=None,
                )
            return JsonResponse(
                {"error": "No se pudo iniciar la carga. Intentá nuevamente."},
                status=502,
            )

        return JsonResponse(
            {
                "archivo_id": archivo.pk,
                "part_size": settings.S3_MULTIPART_PART_SIZE,
                "partes": urls,
            }
        )


class CompletarArchivoView(AdminRequeridoMixin, View):
    """Completa el objeto, verifica tamaño y SHA-256 y confirma el metadato."""

    def post(self, request, archivo_id):
        archivo = get_object_or_404(
            Archivo,
            pk=archivo_id,
            estado=EstadoArchivo.CARGANDO,
        )
        data = _leer_json(request)
        partes = _normalizar_partes(
            data.get("partes") if data else None,
            archivo.cantidad_partes,
        )
        if partes is None:
            return JsonResponse({"error": "La lista de partes es inválida."}, status=400)

        objeto_completado = False
        try:
            resultado = completar_multipart_upload(
                archivo.ruta_almacenamiento,
                archivo.upload_id,
                partes,
            )
            objeto_completado = True
            if resultado["tamano"] != archivo.tamano:
                eliminar_objeto(archivo.ruta_almacenamiento)
                Archivo.objects.filter(pk=archivo.pk).update(
                    estado=EstadoArchivo.INCORRECTO,
                    upload_id=None,
                )
                return JsonResponse(
                    {"error": "El tamaño recibido no coincide con el archivo seleccionado."},
                    status=400,
                )

            hash_sha256 = calcular_sha256_objeto(archivo.ruta_almacenamiento)
            with transaction.atomic():
                archivo = Archivo.objects.select_for_update().get(pk=archivo.pk)
                archivo.hash_sha256 = hash_sha256
                archivo.estado = EstadoArchivo.COMPLETO
                archivo.upload_id = None
                archivo.save(
                    update_fields=["hash_sha256", "estado", "upload_id", "updated_at"]
                )
                LogActividad.objects.create(
                    usuario=request.user,
                    estudio=archivo.estudio,
                    tipo_evento=TipoEvento.CARGA,
                    resultado="Carga completada",
                    detalles=f"Archivo {archivo.pk}; {archivo.tamano} bytes.",
                )
        except Exception:
            logger.exception("No se pudo completar o verificar la carga multipartes.")
            if objeto_completado:
                try:
                    eliminar_objeto(archivo.ruta_almacenamiento)
                except Exception:
                    logger.exception("No se pudo limpiar el objeto inválido.")
            else:
                abortar_multipart_upload(
                    archivo.ruta_almacenamiento,
                    archivo.upload_id,
                )
            Archivo.objects.filter(pk=archivo.pk).update(
                estado=EstadoArchivo.INCORRECTO,
                upload_id=None,
            )
            return JsonResponse(
                {"error": "No se pudo verificar la carga. Volvé a intentarlo."},
                status=502,
            )

        return JsonResponse({"status": "ok", "archivo_id": archivo.pk})


class CancelarArchivoView(AdminRequeridoMixin, View):
    """Aborta una carga incompleta y conserva su resultado para trazabilidad."""

    def post(self, request, archivo_id):
        archivo = get_object_or_404(
            Archivo,
            pk=archivo_id,
            estado=EstadoArchivo.CARGANDO,
        )
        confirmado = abortar_multipart_upload(
            archivo.ruta_almacenamiento,
            archivo.upload_id,
        )
        archivo.estado = EstadoArchivo.INCORRECTO
        archivo.upload_id = None
        archivo.save(update_fields=["estado", "upload_id", "updated_at"])
        if not confirmado:
            logger.warning("S3 no confirmó la cancelación del archivo %s.", archivo.pk)
        return JsonResponse({"status": "cancelado", "archivo_id": archivo.pk})
