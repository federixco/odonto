"""Endpoints autenticados para coordinar cargas directas a S3/MinIO."""

import json
import logging
import math
import uuid
from time import monotonic
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.auditoria.models import LogActividad
from apps.core.enums import (
    CategoriaArchivo,
    EstadoAcceso,
    EstadoArchivo,
    EstadoEstudio,
    FormatoArchivo,
    RolUsuario,
    TipoEvento,
)
from apps.core.mixins import AdminRequeridoMixin
from apps.core.carga_log import registrar_carga
from apps.estudios.models import Estudio

from .models import Archivo
from .services.storage import (
    abortar_multipart_upload,
    calcular_sha256_objeto,
    completar_multipart_upload,
    eliminar_objeto,
    generar_url_descarga,
    generar_url_previsualizacion,
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


def _marcar_incorrecto_y_revisar(archivo, usuario):
    """Conserva el archivo, abre la corrección y corta accesos publicados."""

    with transaction.atomic():
        estudio = Estudio.objects.select_for_update().get(pk=archivo.estudio_id)
        archivo = Archivo.objects.select_for_update().get(pk=archivo.pk)
        if estudio.estado == EstadoEstudio.ELIMINADO:
            raise ValueError("El estudio está eliminado.")
        if archivo.estado != EstadoArchivo.COMPLETO:
            raise ValueError("Solo se puede marcar un archivo completo como incorrecto.")

        estaba_publicado = estudio.estado == EstadoEstudio.PUBLICADO
        archivo.estado = EstadoArchivo.INCORRECTO
        archivo.save(update_fields=["estado", "updated_at"])
        estudio.marcar_en_revision()

        revocadas = 0
        if estaba_publicado:
            autorizaciones = estudio.autorizaciones.select_for_update().filter(
                estado_acceso=EstadoAcceso.VIGENTE
            )
            for autorizacion in autorizaciones:
                autorizacion.revocar(usuario)
                revocadas += 1
                LogActividad.objects.create(
                    usuario=usuario,
                    estudio=estudio,
                    tipo_evento=TipoEvento.REVOCACION,
                    resultado="Acceso revocado temporalmente por corrección",
                    detalles=(
                        f"Autorización {autorizacion.pk}; archivo incorrecto {archivo.pk}."
                    ),
                )

        LogActividad.objects.create(
            usuario=usuario,
            estudio=estudio,
            tipo_evento=TipoEvento.CORRECCION,
            resultado="Archivo marcado como incorrecto",
            detalles=(
                f"Archivo {archivo.pk} ({archivo.nombre_archivo}); "
                f"accesos revocados: {revocadas}."
            ),
        )
    return archivo, revocadas


from apps.core.concurrencia import transferencia_exclusiva


class IniciarArchivoView(AdminRequeridoMixin, View):
    """Crea el registro transitorio y entrega permisos de subida temporales."""

    @transferencia_exclusiva(lambda request, estudio_id: f"iniciar-archivo-estudio:{estudio_id}")
    def post(self, request, estudio_id):
        estudio = get_object_or_404(Estudio, pk=estudio_id)
        if estudio.estado not in {EstadoEstudio.BORRADOR, EstadoEstudio.EN_REVISION}:
            return JsonResponse(
                {"error": "Solo se pueden cargar archivos en estudios editables."},
                status=409,
            )

        data = _leer_json(request)
        clasificacion = _clasificar_nombre(data.get("nombre_archivo") if data else None)
        if data and data.get("solicitud_id") and clasificacion:
            try:
                clave_previa = f"estudios/{estudio.pk}/archivos/{uuid.UUID(data['solicitud_id']).hex}{clasificacion[1]}"
                tamano_previo = int(data.get("tamano", 0))
            except (ValueError, TypeError, AttributeError):
                return JsonResponse({"error": "Solicitud de carga inválida."}, status=400)
            previo = Archivo.objects.filter(estudio=estudio, ruta_almacenamiento=clave_previa).first()
            if previo and previo.estado in {EstadoArchivo.CARGANDO, EstadoArchivo.COMPLETO}:
                if previo.nombre_archivo != clasificacion[0] or previo.tamano != tamano_previo or str(previo.archivo_reemplazado_id or "") != str(data.get("archivo_reemplazado") or ""):
                    return JsonResponse({"error": "La solicitud corresponde a otro archivo."}, status=409)
                from apps.core.concurrencia import bloquear_recurso, RecursoOcupado
                try:
                    with bloquear_recurso(f"archivo:{previo.pk}"):
                        previo.refresh_from_db()
                        if previo.estado == EstadoArchivo.COMPLETO:
                            return JsonResponse({"status": "completo", "archivo_id": previo.pk})
                        if previo.estado == EstadoArchivo.CARGANDO and previo.upload_id:
                            return JsonResponse({"archivo_id": previo.pk, "part_size": settings.S3_MULTIPART_PART_SIZE,
                                "partes": generar_urls_prefirmadas(clave_previa, previo.upload_id, previo.cantidad_partes), "carga_token": previo.upload_id})
                        if previo.estado == EstadoArchivo.CARGANDO and not previo.upload_id:
                            # La exclusión del iniciador garantiza que no hay otro
                            # inicio activo: recuperar una reserva sin upload_id.
                            previo.estado = EstadoArchivo.INCORRECTO
                            previo.save(update_fields=["estado", "updated_at"])
                except RecursoOcupado:
                    return JsonResponse({"error": "Archivo en proceso.", "reintentable": True}, status=409)
        archivo_reemplazado = None
        reemplazado_id = data.get("archivo_reemplazado") if data else None
        if reemplazado_id not in {None, ""}:
            archivo_reemplazado = Archivo.objects.filter(
                pk=reemplazado_id,
                estudio=estudio,
                estado=EstadoArchivo.INCORRECTO,
            ).first()
            if archivo_reemplazado is None:
                return JsonResponse(
                    {"error": "El archivo a reemplazar no existe o ya fue reemplazado."},
                    status=409,
                )
            reemplazo_activo = archivo_reemplazado.reemplazos.filter(
                estado__in=[EstadoArchivo.CARGANDO, EstadoArchivo.COMPLETO]
            ).exists()
            if reemplazo_activo:
                return JsonResponse(
                    {"error": "Ese archivo ya tiene un reemplazo en proceso."},
                    status=409,
                )
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
        ruta_relativa = ""
        if archivo_reemplazado and archivo_reemplazado.ruta_relativa:
            # Conservar la carpeta, usando el nombre del nuevo archivo. No
            # copiar importacion: el histórico conserva su ruta única en el lote.
            ruta_anterior = PurePosixPath(archivo_reemplazado.ruta_relativa.replace("\\", "/"))
            ruta_relativa = str(ruta_anterior.parent / nombre)
            if len(ruta_relativa) > 500:
                return JsonResponse({"error": "La ruta del reemplazo es demasiado larga."}, status=400)
            misma_ruta = Q(ruta_relativa=ruta_relativa)
            if ruta_anterior.parent == PurePosixPath("."):
                misma_ruta |= Q(ruta_relativa="", nombre_archivo=nombre)
            if estudio.archivos.filter(
                misma_ruta, estado__in=[EstadoArchivo.CARGANDO, EstadoArchivo.COMPLETO],
            ).exists():
                return JsonResponse({"error": "Ya existe un archivo vigente en esa ruta."}, status=409)
        cantidad_partes = math.ceil(tamano / settings.S3_MULTIPART_PART_SIZE)
        if cantidad_partes > S3_MAX_PARTS:
            return JsonResponse({"error": "El archivo requiere demasiadas partes."}, status=400)

        clave_objeto = (
            f"estudios/{estudio.pk}/archivos/{uuid.uuid4().hex}{extension}"
        )
        solicitud = data.get("solicitud_id")
        existente = None
        if solicitud:
            try:
                identificador = uuid.UUID(solicitud).hex
            except (ValueError, TypeError, AttributeError):
                return JsonResponse({"error": "Identificador de solicitud inválido."}, status=400)
            clave_objeto = f"estudios/{estudio.pk}/archivos/{identificador}{extension}"
            existente = Archivo.objects.filter(estudio=estudio, ruta_almacenamiento=clave_objeto).first()
            if existente:
                if existente.tamano != tamano or existente.nombre_archivo != nombre or existente.archivo_reemplazado_id != (archivo_reemplazado.pk if archivo_reemplazado else None):
                    return JsonResponse({"error": "La solicitud corresponde a otro archivo."}, status=409)
                from apps.core.concurrencia import bloquear_recurso, RecursoOcupado
                try:
                    with bloquear_recurso(f"archivo:{existente.pk}"):
                        existente.refresh_from_db()
                        if existente.estado == EstadoArchivo.COMPLETO:
                            return JsonResponse({"status": "completo", "archivo_id": existente.pk})
                        if existente.estado == EstadoArchivo.CARGANDO and existente.upload_id:
                            return JsonResponse({"archivo_id": existente.pk, "part_size": settings.S3_MULTIPART_PART_SIZE,
                                "partes": generar_urls_prefirmadas(clave_objeto, existente.upload_id, existente.cantidad_partes), "carga_token": existente.upload_id})
                        if existente.estado != EstadoArchivo.INCORRECTO:
                            return JsonResponse({"error": "Este archivo no admite reintentos."}, status=409)
                        if existente.upload_id and not abortar_multipart_upload(clave_objeto, existente.upload_id):
                            return JsonResponse({"error": "La limpieza sigue pendiente.", "reintentable": True}, status=503)
                        eliminar_objeto(clave_objeto)
                except RecursoOcupado:
                    return JsonResponse({"error": "Archivo en proceso.", "reintentable": True}, status=409)
                except Exception:
                    logger.exception("No se pudo renovar la carga %s", existente.pk)
                    return JsonResponse({"error": "No se pudo renovar la carga.", "reintentable": True}, status=503)
        upload_id = None
        confirmado = True
        archivo = None
        inicio = monotonic()
        registrar_carga("archivo_inicio_solicitado", estudio_id=estudio.pk, bytes_total=tamano, partes=cantidad_partes)
        try:
            archivo = existente or Archivo(
                estudio=estudio,
                nombre_archivo=nombre,
                ruta_relativa=ruta_relativa,
                formato=formato,
                categoria=categoria,
                ruta_almacenamiento=clave_objeto,
                tamano=tamano,
                upload_id=upload_id,
                content_type=content_type,
                cantidad_partes=cantidad_partes,
                estado=EstadoArchivo.CARGANDO,
                archivo_reemplazado=archivo_reemplazado,
            )
            archivo.upload_id, archivo.estado = upload_id, EstadoArchivo.CARGANDO
            archivo.hash_sha256 = None
            with transaction.atomic():
                actual = Estudio.objects.select_for_update().get(pk=estudio.pk)
                if actual.estado not in {EstadoEstudio.BORRADOR, EstadoEstudio.EN_REVISION}:
                    raise ValueError("El estudio ya no admite cargas.")
                if archivo_reemplazado and not Archivo.objects.filter(pk=archivo_reemplazado.pk, estado=EstadoArchivo.INCORRECTO).exists():
                    raise ValueError("El archivo anterior ya fue reemplazado.")
                archivo.save()
            # Reservar antes del I/O impide que se publique el estudio mientras
            # S3 todavía está preparando el archivo.
            upload_id = iniciar_multipart_upload(clave_objeto, content_type)
            with transaction.atomic():
                actual = Estudio.objects.select_for_update().get(pk=estudio.pk)
                actual_archivo = Archivo.objects.select_for_update().get(pk=archivo.pk)
                if actual.estado not in {EstadoEstudio.BORRADOR, EstadoEstudio.EN_REVISION} or actual_archivo.estado != EstadoArchivo.CARGANDO:
                    raise ValueError("La carga fue cancelada o el estudio dejó de ser editable.")
                archivo.upload_id = upload_id
                archivo.save(update_fields=["upload_id", "updated_at"])
            urls = generar_urls_prefirmadas(
                clave_objeto,
                upload_id,
                cantidad_partes,
            )
        except Exception as error:
            registrar_carga("archivo_inicio_error", estudio_id=estudio.pk,
                            archivo_id=archivo.pk if archivo else None, error=error)
            logger.exception("No se pudo iniciar la carga multipartes.")
            if upload_id:
                confirmado = abortar_multipart_upload(clave_objeto, upload_id)
            if archivo and archivo.pk:
                Archivo.objects.filter(pk=archivo.pk).update(
                    estado=EstadoArchivo.INCORRECTO,
                    upload_id=None if confirmado else upload_id,
                )
            return JsonResponse(
                {"error": "No se pudo iniciar la carga. Intentá nuevamente."},
                status=502,
            )

        registrar_carga("archivo_carga_habilitada", estudio_id=estudio.pk, archivo_id=archivo.pk,
                        bytes_total=tamano, partes=cantidad_partes, duracion_ms=round((monotonic() - inicio) * 1000))
        return JsonResponse(
            {
                "archivo_id": archivo.pk,
                "part_size": settings.S3_MULTIPART_PART_SIZE,
                "partes": urls,
                "carga_token": upload_id,
            }
        )


class CompletarArchivoView(AdminRequeridoMixin, View):
    """Completa el objeto, verifica tamaño y SHA-256 y confirma el metadato."""

    @transferencia_exclusiva(lambda request, archivo_id: f"archivo:{archivo_id}")
    def post(self, request, archivo_id):
        archivo = get_object_or_404(
            Archivo,
            pk=archivo_id,
            estudio__isnull=False,
        )
        if archivo.estado == EstadoArchivo.COMPLETO:
            return JsonResponse({"status": "ok", "archivo_id": archivo.pk})
        if archivo.estado != EstadoArchivo.CARGANDO:
            return JsonResponse({"error": "Esta carga ya no está vigente."}, status=409)
        if not archivo.upload_id:
            return JsonResponse({"error": "La carga todavía se está preparando.", "reintentable": True}, status=409)
        data = _leer_json(request)
        if data and data.get("carga_token", archivo.upload_id) != archivo.upload_id:
            return JsonResponse({"error": "El intento de carga fue reemplazado."}, status=409)
        partes = _normalizar_partes(
            data.get("partes") if data else None,
            archivo.cantidad_partes,
        )
        if partes is None:
            return JsonResponse({"error": "La lista de partes es inválida."}, status=400)

        objeto_completado = False
        inicio = monotonic()
        registrar_carga("archivo_verificacion_iniciada", estudio_id=archivo.estudio_id, archivo_id=archivo.pk)
        try:
            resultado = completar_multipart_upload(
                archivo.ruta_almacenamiento,
                archivo.upload_id,
                partes,
            )
            objeto_completado = True
            if resultado["tamano"] != archivo.tamano:
                registrar_carga("archivo_tamano_incorrecto", estudio_id=archivo.estudio_id,
                                archivo_id=archivo.pk, error=ValueError())
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
                estudio = Estudio.objects.select_for_update().get(pk=archivo.estudio_id)
                request.comprobar_bloqueo_transferencia()
                if estudio.estado not in {EstadoEstudio.BORRADOR, EstadoEstudio.EN_REVISION}:
                    raise ValueError("El estudio ya no admite cargas.")
                archivo = Archivo.objects.select_for_update().get(pk=archivo.pk)
                if archivo.estado != EstadoArchivo.CARGANDO:
                    raise ValueError("La carga ya no está vigente.")
                archivo.hash_sha256 = hash_sha256
                archivo.estado = EstadoArchivo.COMPLETO
                archivo.upload_id = None
                archivo.save(
                    update_fields=["hash_sha256", "estado", "upload_id", "updated_at"]
                )
                es_reemplazo = archivo.archivo_reemplazado_id is not None
                if es_reemplazo:
                    archivo.estudio.reemplazar_archivo(
                        archivo.archivo_reemplazado_id,
                        archivo,
                    )
                LogActividad.objects.create(
                    usuario=request.user,
                    estudio=archivo.estudio,
                    tipo_evento=(
                        TipoEvento.CORRECCION if es_reemplazo else TipoEvento.CARGA
                    ),
                    resultado=(
                        "Archivo reemplazado" if es_reemplazo else "Carga completada"
                    ),
                    detalles=(
                        f"Archivo nuevo {archivo.pk}; reemplaza a "
                        f"{archivo.archivo_reemplazado_id}; {archivo.tamano} bytes."
                        if es_reemplazo
                        else f"Archivo {archivo.pk}; {archivo.tamano} bytes."
                    ),
                )
        except Exception as error:
            registrar_carga("archivo_verificacion_error", estudio_id=archivo.estudio_id, archivo_id=archivo.pk, error=error)
            logger.exception("No se pudo completar o verificar la carga multipartes.")
            request.comprobar_bloqueo_transferencia()
            if objeto_completado:
                try:
                    eliminar_objeto(archivo.ruta_almacenamiento)
                except Exception:
                    logger.exception("No se pudo limpiar el objeto inválido.")
            else:
                abortado = abortar_multipart_upload(
                    archivo.ruta_almacenamiento,
                    archivo.upload_id,
                )
            Archivo.objects.filter(pk=archivo.pk).update(
                estado=EstadoArchivo.INCORRECTO,
                upload_id=None if objeto_completado or abortado else archivo.upload_id,
            )
            return JsonResponse(
                {"error": "No se pudo verificar la carga. Volvé a intentarlo."},
                status=502,
            )

        registrar_carga("archivo_completo", estudio_id=archivo.estudio_id, archivo_id=archivo.pk,
                        bytes_total=archivo.tamano, duracion_ms=round((monotonic() - inicio) * 1000))
        return JsonResponse({"status": "ok", "archivo_id": archivo.pk})


class CancelarArchivoView(AdminRequeridoMixin, View):
    """Aborta una carga incompleta y conserva su resultado para trazabilidad."""

    @transferencia_exclusiva(lambda request, archivo_id: f"archivo:{archivo_id}")
    def post(self, request, archivo_id):
        archivo = get_object_or_404(
            Archivo,
            pk=archivo_id,
            estudio__isnull=False,
        )
        if archivo.estado == EstadoArchivo.COMPLETO:
            return JsonResponse({"status": "completo", "archivo_id": archivo.pk})
        if archivo.estado not in {EstadoArchivo.CARGANDO, EstadoArchivo.INCORRECTO}:
            return JsonResponse({"error": "El archivo no es una carga cancelable."}, status=409)
        if not archivo.upload_id:
            archivo.estado = EstadoArchivo.INCORRECTO
            archivo.save(update_fields=["estado", "updated_at"])
            return JsonResponse({"status": "cancelado", "archivo_id": archivo.pk})
        confirmado = abortar_multipart_upload(
            archivo.ruta_almacenamiento,
            archivo.upload_id,
        )
        if confirmado:
            try:
                eliminar_objeto(archivo.ruta_almacenamiento)
            except Exception:
                confirmado = False
                logger.exception("No se pudo limpiar la carga cancelada %s", archivo.pk)
        archivo.estado = EstadoArchivo.INCORRECTO
        archivo.upload_id = None if confirmado else archivo.upload_id
        archivo.save(update_fields=["estado", "upload_id", "updated_at"])
        if not confirmado:
            logger.warning("S3 no confirmó la cancelación del archivo %s.", archivo.pk)
        return JsonResponse({"status": "cancelado" if confirmado else "limpieza_pendiente", "archivo_id": archivo.pk}, status=200 if confirmado else 503)


class MarcarArchivoIncorrectoView(AdminRequeridoMixin, View):
    """Inicia una corrección sin borrar el archivo ni su objeto almacenado."""

    def post(self, request, archivo_id):
        archivo = get_object_or_404(
            Archivo.objects.select_related("estudio"),
            pk=archivo_id,
            estudio__isnull=False,
        )
        try:
            _, revocadas = _marcar_incorrecto_y_revisar(archivo, request.user)
        except ValueError as error:
            messages.error(request, str(error))
        else:
            mensaje = "El archivo quedó marcado como incorrecto."
            if revocadas:
                mensaje += f" Se revocaron temporalmente {revocadas} acceso(s)."
            messages.success(request, mensaje)
        return redirect("estudio_detalle", pk=archivo.estudio_id)


class EliminarArchivoView(AdminRequeridoMixin, View):
    """Compatibilidad: convierte el borrado anterior en corrección trazable."""

    def post(self, request, archivo_id):
        archivo = get_object_or_404(Archivo, pk=archivo_id, estudio__isnull=False)
        
        try:
            _marcar_incorrecto_y_revisar(archivo, request.user)
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=409)
        return JsonResponse({"status": "marcado_incorrecto"})


class DescargarArchivoView(View):
    """Entrega únicamente archivos completos de un estudio autorizado."""

    def get(self, request, archivo_id):
        if not request.user.is_authenticated:
            return redirect("login")

        archivo = get_object_or_404(
            Archivo.objects.select_related("estudio", "estudio__paciente"),
            pk=archivo_id,
            estado=EstadoArchivo.COMPLETO,
        )
        estudio = archivo.estudio
        if not estudio:
            raise Http404("El archivo no está asociado a ningún estudio.")

        # Validación de permisos por rol
        rol = request.user.rol
        if rol == RolUsuario.PACIENTE:
            if estudio.estado != EstadoEstudio.PUBLICADO:
                raise PermissionDenied("El estudio no se encuentra publicado.")
            try:
                paciente = request.user.paciente
            except Exception:
                raise PermissionDenied("La cuenta no está asociada a una ficha clínica.")

            if estudio.paciente_id != paciente.pk:
                raise PermissionDenied("No tenés acceso a los archivos de este estudio.")

        elif rol == RolUsuario.ODONTOLOGO:
            # Debe existir una autorización vigente para este estudio y odontólogo
            if estudio.estado != EstadoEstudio.PUBLICADO:
                raise PermissionDenied("El estudio no está publicado.")

            from apps.accesos.models import Autorizacion
            try:
                odontologo = request.user.odontologo
            except Exception:
                raise PermissionDenied("La cuenta no está asociada a un odontólogo.")

            autorizado = Autorizacion.objects.filter(
                estudio=estudio,
                odontologo=odontologo,
                estado_acceso=EstadoAcceso.VIGENTE,
            ).exists()
            if not autorizado:
                raise PermissionDenied("No tenés autorización vigente para descargar archivos de este estudio.")

        elif rol == RolUsuario.ADMINISTRADOR:
            # El administrador del centro tiene acceso completo
            pass
        else:
            raise PermissionDenied("Rol no autorizado.")

        # Registrar auditoría de descarga
        LogActividad.objects.create(
            usuario=request.user,
            estudio=estudio,
            tipo_evento=TipoEvento.DESCARGA,
            resultado="Descarga iniciada",
            detalles=f"Descarga de archivo {archivo.nombre_archivo} ({archivo.pk}) de {archivo.tamano} bytes.",
        )

        # Generar URL prefirmada con cabecera attachment
        url_descarga = generar_url_descarga(
            clave_objeto=archivo.ruta_almacenamiento,
            nombre_archivo=archivo.nombre_archivo,
        )
        return HttpResponseRedirect(url_descarga)


class PrevisualizarArchivoView(View):
    """Permite previsualizar en el navegador archivos compatibles (JPG, PNG, TIFF, PDF).
    Accesible por Administrador, Odontólogo autorizado, y Paciente titular de la ficha clínica.
    """

    FORMATOS_PREVISUALIZABLES = {
        FormatoArchivo.JPG,
        FormatoArchivo.PNG,
        FormatoArchivo.TIFF,
        FormatoArchivo.PDF,
    }

    def get(self, request, archivo_id):
        if not request.user.is_authenticated:
            return redirect("login")

        archivo = get_object_or_404(
            Archivo.objects.select_related("estudio", "estudio__paciente"),
            pk=archivo_id,
            estado=EstadoArchivo.COMPLETO,
        )
        estudio = archivo.estudio
        if not estudio:
            raise Http404("El archivo no está asociado a ningún estudio.")

        if archivo.formato not in self.FORMATOS_PREVISUALIZABLES:
            raise Http404("Este formato de archivo no admite previsualización directa en el navegador.")

        rol = request.user.rol
        if rol == RolUsuario.ADMINISTRADOR:
            pass
        elif rol == RolUsuario.ODONTOLOGO:
            if estudio.estado != EstadoEstudio.PUBLICADO:
                raise PermissionDenied("El estudio no está publicado.")
            from apps.accesos.models import Autorizacion
            try:
                odontologo = request.user.odontologo
            except Exception:
                raise PermissionDenied("La cuenta no está asociada a un odontólogo.")

            autorizado = Autorizacion.objects.filter(
                estudio=estudio,
                odontologo=odontologo,
                estado_acceso=EstadoAcceso.VIGENTE,
            ).exists()
            if not autorizado:
                raise PermissionDenied("No tenés autorización vigente para visualizar este estudio.")
        elif rol == RolUsuario.PACIENTE:
            if estudio.estado != EstadoEstudio.PUBLICADO:
                raise PermissionDenied("El estudio no está publicado.")
            try:
                paciente = request.user.paciente
            except Exception:
                raise PermissionDenied("La cuenta no está asociada a una ficha de paciente.")

            if estudio.paciente_id != paciente.pk:
                raise PermissionDenied("No podés acceder a estudios que no te pertenecen.")
        else:
            raise PermissionDenied("Rol no autorizado.")

        # Registrar auditoría de visualización
        LogActividad.objects.create(
            usuario=request.user,
            estudio=estudio,
            tipo_evento=TipoEvento.VISUALIZACION,
            resultado="Visualización de archivo",
            detalles=f"Previsualización de {archivo.nombre_archivo} ({archivo.pk}).",
        )

        url_inline = generar_url_previsualizacion(
            clave_objeto=archivo.ruta_almacenamiento,
            content_type=archivo.content_type,
        )
        return HttpResponseRedirect(url_inline)

