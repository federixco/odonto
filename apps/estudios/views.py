from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo
from django.db.models import Count, Sum
import json
import logging
import math
import uuid
from time import monotonic
from pathlib import Path, PurePosixPath

import tempfile
import shutil
import zipfile
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView
from django.views.generic.detail import SingleObjectMixin

from apps.archivos.models import Archivo
from apps.core.carga_log import registrar_carga
from apps.archivos.services.storage import (
    abortar_multipart_upload,
    calcular_sha256_objeto,
    completar_multipart_upload,
    eliminar_objeto,
    generar_urls_prefirmadas,
    get_s3_client,
    iniciar_multipart_upload,
)
from apps.accesos.models import Autorizacion
from apps.auditoria.models import LogActividad
from apps.core.enums import CategoriaArchivo, EstadoAcceso, EstadoArchivo, EstadoCuenta, EstadoEstudio, EstadoImportacion, FormatoArchivo, TipoEvento
from apps.core.mixins import AdminRequeridoMixin, EstudioAccesoMixin
from .forms import (
    ConfirmarImportacionForm,
    EstudioForm,
    RegistrarPacienteDetectadoForm,
)
from .models import Estudio, ImportacionEstudio
from .services.importador import analizar_importacion
from .services.explorador import contexto_archivos
from apps.core.concurrencia import bloquear_recurso, RecursoOcupado, transferencia_exclusiva
from .services.trabajos import encolar


# Errores del proveedor: registrar mensajes estáticos/IDs, nunca exc_info ni URLs.
logger = logging.getLogger(__name__)
S3_MIN_PART_SIZE = 5 * 1024 * 1024
S3_MAX_PARTS = 10_000
ZIP_CHUNK_SIZE = 1024 * 1024


def _leer_json(request):
    try:
        data = json.loads(request.body)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _partes_validas(partes, cantidad):
    if not isinstance(partes, list) or len(partes) != cantidad:
        return None
    salida = []
    for parte in partes:
        if not isinstance(parte, dict) or type(parte.get("PartNumber")) is not int or not isinstance(parte.get("ETag"), str) or not parte["ETag"].strip() or len(parte["ETag"]) > 1024:
            return None
        salida.append({"PartNumber": parte["PartNumber"], "ETag": parte["ETag"]})
    salida.sort(key=lambda p: p["PartNumber"])
    return salida if [p["PartNumber"] for p in salida] == list(range(1, cantidad + 1)) else None


def _ruta_importada_valida(ruta):
    if not isinstance(ruta, str) or not ruta.strip() or len(ruta) > 500 or any(ord(c) < 32 for c in ruta):
        return None
    normalizada = ruta.replace("\\", "/")
    parsed = PurePosixPath(normalizada)
    if parsed.is_absolute() or ".." in parsed.parts or (parsed.parts and ":" in parsed.parts[0]):
        return None
    return parsed.as_posix()


def _clasificar_importado(nombre):
    extension = Path(nombre).suffix.lower()
    conocidos = {
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
        ".gwg": (FormatoArchivo.GALILEOS, CategoriaArchivo.PAQUETE_PROPIETARIO, "application/octet-stream"),
    }
    return extension, *conocidos.get(extension, (FormatoArchivo.OTRO, CategoriaArchivo.PAQUETE_PROPIETARIO, "application/octet-stream"))

class ListaEstudiosView(AdminRequeridoMixin, ListView):
    """Listado de todos los estudios con opción de agruparlos como explorador."""
    
    template_name = "estudios/estudio_lista.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        self.agrupar = self.request.GET.get("agrupar", "").strip()
        self.carpeta_id = self.request.GET.get("carpeta_id", "").strip()
        busqueda = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "").strip()
        
        # 1. Agrupar por Paciente (Nivel Raíz)
        if self.agrupar == "paciente" and not self.carpeta_id:
            filtro = Q(estudios__estado=estado) if estado in EstadoEstudio.values else None
            qs = Paciente.objects.annotate(num_estudios=Count("estudios", filter=filtro)).filter(num_estudios__gt=0)
            if busqueda:
                qs = qs.filter(Q(nombre__icontains=busqueda) | Q(apellido__icontains=busqueda) | Q(dni__icontains=busqueda))
            return qs.order_by("apellido", "nombre", "pk")
            
        # 2. Agrupar por Odontólogo (Nivel Raíz)
        if self.agrupar == "odontologo" and not self.carpeta_id:
            filtro = Q(autorizaciones__estudio__estado=estado) if estado in EstadoEstudio.values else None
            qs = Odontologo.objects.annotate(num_estudios=Count("autorizaciones__estudio", filter=filtro, distinct=True)).filter(num_estudios__gt=0)
            if busqueda:
                qs = qs.filter(Q(nombre__icontains=busqueda) | Q(apellido__icontains=busqueda) | Q(matricula__icontains=busqueda))
            return qs.order_by("apellido", "nombre", "pk")

        # 3. Listado de Estudios (Plano o dentro de una carpeta)
        qs = Estudio.objects.select_related("paciente").order_by("-fecha_estudio", "-created_at", "-pk")
        
        if self.agrupar == "paciente" and self.carpeta_id:
            qs = qs.filter(paciente_id=self.carpeta_id)
        elif self.agrupar == "odontologo" and self.carpeta_id:
            qs = qs.filter(autorizaciones__odontologo_id=self.carpeta_id)
            
        if busqueda:
            qs = qs.filter(
                Q(paciente__nombre__icontains=busqueda)
                | Q(paciente__apellido__icontains=busqueda)
                | Q(paciente__dni__icontains=busqueda)
                | Q(tipo__icontains=busqueda)
            )
        if estado and estado in EstadoEstudio.values:
            qs = qs.filter(estado=estado)
            
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["busqueda"] = self.request.GET.get("q", "")
        contexto["estado_filtro"] = self.request.GET.get("estado", "")
        contexto["estados"] = EstadoEstudio.choices
        contexto["agrupar"] = self.agrupar
        contexto["carpeta_id"] = self.carpeta_id
        
        # Determinar el tipo de elementos actuales y armar el breadcrumb
        contexto["breadcrumb"] = [{"nombre": "Todos los estudios", "url": "?agrupar="}]
        
        if self.agrupar == "paciente":
            contexto["tipo_items"] = "carpetas_pacientes" if not self.carpeta_id else "estudios"
            contexto["breadcrumb"] = [{"nombre": "Pacientes", "url": "?agrupar=paciente"}]
            if self.carpeta_id:
                paciente = get_object_or_404(Paciente, pk=self.carpeta_id)
                contexto["breadcrumb"].append({"nombre": f"{paciente.nombre} {paciente.apellido}", "url": ""})
                contexto["carpeta_obj"] = paciente
                
        elif self.agrupar == "odontologo":
            contexto["tipo_items"] = "carpetas_odontologos" if not self.carpeta_id else "estudios"
            contexto["breadcrumb"] = [{"nombre": "Odontólogos", "url": "?agrupar=odontologo"}]
            if self.carpeta_id:
                odontologo = get_object_or_404(Odontologo, pk=self.carpeta_id)
                contexto["breadcrumb"].append({"nombre": f"Dr/a. {odontologo.apellido}", "url": ""})
                contexto["carpeta_obj"] = odontologo
        else:
            contexto["tipo_items"] = "estudios"
            
        return contexto


class CrearEstudioView(AdminRequeridoMixin, View):
    """
    Vista para que el administrador inicie un nuevo estudio.
    Crea el Estudio en estado BORRADOR y redirige al detalle
    para continuar con la subida de archivos (Etapa 3).
    """
    def get(self, request):
        return render(request, "estudios/estudio_crear.html", {"form": EstudioForm()})

    def post(self, request):
        form = EstudioForm(request.POST)
        if form.is_valid():
            estudio = form.save(commit=False)
            # El estado por defecto es BORRADOR
            estudio.save()
            messages.success(request, "Estudio creado. Ahora podés subir sus archivos.")
            return redirect("estudio_detalle", pk=estudio.pk)
        return render(request, "estudios/estudio_crear.html", {"form": form})

class DetalleEstudioView(AdminRequeridoMixin, DetailView):
    """Resume el estudio, sus archivos y los profesionales con acceso."""

    model = Estudio
    template_name = "estudios/estudio_detalle.html"
    context_object_name = "estudio"

    def get_queryset(self):
        return Estudio.objects.select_related("paciente")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        archivos = self.object.archivos.order_by("ruta_relativa", "nombre_archivo", "pk")
        contexto.update(contexto_archivos(archivos, self.request.GET.get("archivos_pagina")))
        contexto["archivos_incorrectos"] = [
            archivo for archivo in contexto["archivos_pagina"].object_list
            if archivo.estado == EstadoArchivo.INCORRECTO
        ]
        contexto["puede_descargar_zip"] = (
            self.object.estado != EstadoEstudio.ELIMINADO
            and archivos.filter(estado=EstadoArchivo.COMPLETO).exists()
        )
        contexto["archivos_pendientes_purga"] = archivos.exclude(
            estado=EstadoArchivo.PURGADO
        ).count()

        contexto["accesos_vigentes"] = self.object.autorizaciones.select_related(
            "odontologo__usuario", "revocado_por"
        ).filter(estado_acceso=EstadoAcceso.VIGENTE).order_by("odontologo__apellido", "odontologo__nombre")
        
        return contexto



class PublicarEstudioView(AdminRequeridoMixin, View):
    """Permite al administrador publicar un estudio manualmente si tiene archivos completos."""
    def post(self, request, pk):
        estudio = get_object_or_404(Estudio.objects.exclude(estado=EstadoEstudio.ELIMINADO), pk=pk)
        try:
            estudio.publicar()
            messages.success(request, "El estudio fue publicado exitosamente.")
            LogActividad.objects.create(
                usuario=request.user,
                estudio=estudio,
                tipo_evento=TipoEvento.PUBLICACION,
                resultado="Estudio publicado manualmente",
                detalles=f"El estudio {estudio.pk} cambi a estado PUBLICADO."
            )
        except ValidationError as e:
            messages.error(request, e.message)
        return redirect("estudio_detalle", pk=estudio.pk)


class AgregarAccesoEstudioView(AdminRequeridoMixin, View):
    """Otorga o reactiva el acceso de un odontólogo a un estudio."""

    def post(self, request, pk):
        estudio = get_object_or_404(
            Estudio.objects.exclude(estado=EstadoEstudio.ELIMINADO),
            pk=pk,
        )
        odontologo = get_object_or_404(
            Odontologo.objects.select_related("usuario"),
            pk=request.POST.get("odontologo"),
            usuario__estado=EstadoCuenta.HABILITADA,
            usuario__is_active=True,
        )

        with transaction.atomic():
            autorizacion, creada = Autorizacion.objects.get_or_create(
                estudio=estudio,
                odontologo=odontologo,
            )
            reactivada = False
            if not creada and autorizacion.estado_acceso == EstadoAcceso.REVOCADO:
                autorizacion.estado_acceso = EstadoAcceso.VIGENTE
                autorizacion.fecha_revocacion = None
                autorizacion.revocado_por = None
                autorizacion.full_clean()
                autorizacion.save(
                    update_fields=[
                        "estado_acceso",
                        "fecha_revocacion",
                        "revocado_por",
                    ]
                )
                reactivada = True
            if creada or reactivada:
                try:
                    estudio.publicar()
                except ValidationError:
                    pass
                LogActividad.objects.create(
                    usuario=request.user,
                    estudio=estudio,
                    tipo_evento=TipoEvento.MODIFICACION_USUARIO,
                    resultado="Acceso otorgado al estudio",
                    detalles=f"Acceso del estudio {estudio.pk} otorgado a {odontologo}.",
                )

        if creada:
            messages.success(request, f"{odontologo} ahora tiene acceso al estudio.")
        elif reactivada:
            messages.success(request, f"Se reactivó el acceso de {odontologo}.")
        else:
            messages.info(request, f"{odontologo} ya tenía acceso al estudio.")
        return redirect("estudio_detalle", pk=estudio.pk)


class RevocarAccesoEstudioView(AdminRequeridoMixin, View):
    """Revoca un acceso sin eliminar su trazabilidad."""

    def post(self, request, pk, autorizacion_id):
        estudio = get_object_or_404(
            Estudio.objects.exclude(estado=EstadoEstudio.ELIMINADO),
            pk=pk,
        )
        autorizacion = get_object_or_404(
            Autorizacion.objects.select_related("odontologo"),
            pk=autorizacion_id,
            estudio=estudio,
        )
        if autorizacion.estado_acceso == EstadoAcceso.REVOCADO:
            messages.info(request, "Ese acceso ya estaba revocado.")
            return redirect("estudio_detalle", pk=estudio.pk)

        with transaction.atomic():
            autorizacion.revocar(request.user)
            LogActividad.objects.create(
                usuario=request.user,
                estudio=estudio,
                tipo_evento=TipoEvento.REVOCACION,
                resultado="Acceso revocado",
                detalles=f"Acceso del estudio {estudio.pk} revocado a {autorizacion.odontologo}.",
            )
        messages.success(
            request,
            f"Se revocó el acceso de {autorizacion.odontologo}.",
        )
        return redirect("estudio_detalle", pk=estudio.pk)


class CrearImportacionView(AdminRequeridoMixin, View):
    """Pantalla para seleccionar una carpeta exportada por el equipo clínico."""

    def get(self, request):
        estudios_recientes = (
            Estudio.objects.select_related("paciente")
            .exclude(estado=EstadoEstudio.ELIMINADO)
            .order_by("-created_at")[:5]
        )
        pendientes = ImportacionEstudio.objects.filter(
            iniciada_por=request.user, 
            estado__in=[EstadoImportacion.PENDIENTE_CONFIRMACION, EstadoImportacion.PROCESANDO, EstadoImportacion.ERROR],
        ).order_by("-created_at", "-pk")[:25]
        
        return render(
            request,
            "estudios/importacion_crear.html",
            {
                "estudios_recientes": estudios_recientes,
                "pendientes": pendientes,
            },
        )


class IniciarImportacionView(AdminRequeridoMixin, View):
    @transferencia_exclusiva(lambda request, **kw: f"iniciar-lote:{request.user.pk}")
    def post(self, request):
        data = _leer_json(request) or {}
        nombre = data.get("nombre_carpeta", "")
        try:
            cantidad = int(data.get("cantidad_archivos", 0))
            tamano = int(data.get("tamano_total", 0))
        except (TypeError, ValueError):
            cantidad = tamano = 0
        if not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 255 or Path(nombre).name != nombre:
            return JsonResponse({"error": "El nombre de la carpeta no es válido."}, status=400)
        if not 1 <= cantidad <= getattr(settings, "IMPORTACION_MAX_ARCHIVOS", 5000) or tamano <= 0 or tamano > getattr(settings, "IMPORTACION_MAX_TAMANO_TOTAL", 10 * 1024**3):
            return JsonResponse({"error": "La carpeta supera los límites permitidos o está vacía."}, status=400)
        solicitud = data.get("solicitud_id")
        if solicitud:
            try:
                solicitud = str(uuid.UUID(solicitud))
            except (ValueError, TypeError, AttributeError):
                return JsonResponse({"error": "Identificador de solicitud inválido."}, status=400)
            anterior = ImportacionEstudio.objects.filter(iniciada_por=request.user, datos_detectados___carga__solicitud_id=solicitud).first()
            if anterior:
                if (anterior.nombre_carpeta, anterior.cantidad_archivos, anterior.tamano_total) != (nombre.strip(), cantidad, tamano):
                    return JsonResponse({"error": "La solicitud corresponde a otra carpeta."}, status=409)
                return JsonResponse({"importacion_id": anterior.pk, "estado": anterior.estado, "detalle_url": f"/estudios/importaciones/{anterior.pk}/"})
        lote = ImportacionEstudio.objects.create(iniciada_por=request.user, nombre_carpeta=nombre.strip(), cantidad_archivos=cantidad, tamano_total=tamano,
            datos_detectados={"_carga": {"solicitud_id": solicitud}})
        registrar_carga("importacion_iniciada", importacion_id=lote.pk, cantidad=cantidad, bytes_total=tamano)
        LogActividad.objects.create(usuario=request.user, tipo_evento=TipoEvento.IMPORTACION_INICIADA, resultado="Importación iniciada", detalles=f"Importación {lote.pk}: {cantidad} archivos, {tamano} bytes.")
        return JsonResponse({"importacion_id": lote.pk, "detalle_url": f"/estudios/importaciones/{lote.pk}/"})


class IniciarArchivoImportadoView(AdminRequeridoMixin, View):
    @transferencia_exclusiva(lambda request, importacion_id: f"iniciar-archivo-lote:{importacion_id}")
    def post(self, request, importacion_id):
        lote = get_object_or_404(ImportacionEstudio, pk=importacion_id, iniciada_por=request.user, estado=EstadoImportacion.CARGANDO)
        data = _leer_json(request) or {}
        ruta = _ruta_importada_valida(data.get("ruta_relativa"))
        try:
            tamano = int(data.get("tamano", 0))
        except (TypeError, ValueError): tamano = 0
        if not ruta or tamano <= 0 or tamano > settings.S3_MAX_UPLOAD_SIZE:
            return JsonResponse({"error": "La ruta o el tamaño del archivo no son válidos."}, status=400)
        if settings.S3_MULTIPART_PART_SIZE < S3_MIN_PART_SIZE:
            return JsonResponse({"error": "Configuración de carga inválida."}, status=500)
        nombre = PurePosixPath(ruta).name
        if len(nombre) > 255:
            return JsonResponse({"error": "El nombre del archivo es demasiado largo."}, status=400)
        extension, formato, categoria, content_type = _clasificar_importado(nombre)
        partes = math.ceil(tamano / settings.S3_MULTIPART_PART_SIZE)
        if partes > S3_MAX_PARTS: return JsonResponse({"error": "El archivo requiere demasiadas partes."}, status=400)
        clave = f"importaciones/{lote.pk}/archivos/{uuid.uuid4().hex}{extension}"
        existente = lote.archivos.filter(ruta_relativa=ruta).first()
        if not existente:
            from django.db.models import Sum
            resumen = lote.archivos.aggregate(cantidad=Count("pk"), bytes=Sum("tamano"))
            if resumen["cantidad"] >= lote.cantidad_archivos or (resumen["bytes"] or 0) + tamano > lote.tamano_total:
                return JsonResponse({"error": "El archivo excede la cantidad o el tamaño declarado para la carpeta."}, status=400)
        if existente:
            if existente.tamano != tamano:
                return JsonResponse({"error": "La misma ruta ya existe con otro tamaño."}, status=409)
            try:
                with bloquear_recurso(f"archivo:{existente.pk}"):
                    existente.refresh_from_db()
                    if existente.estado == EstadoArchivo.COMPLETO:
                        return JsonResponse({"archivo_id": existente.pk, "status": "completo"})
                    if existente.estado == EstadoArchivo.CARGANDO and existente.upload_id:
                        urls = generar_urls_prefirmadas(existente.ruta_almacenamiento, existente.upload_id, existente.cantidad_partes)
                        return JsonResponse({"archivo_id": existente.pk, "part_size": settings.S3_MULTIPART_PART_SIZE, "partes": urls, "carga_token": existente.upload_id})
                    if existente.estado != EstadoArchivo.INCORRECTO:
                        return JsonResponse({"error": "Este archivo no admite reintentos."}, status=409)
                    if existente.upload_id and not abortar_multipart_upload(existente.ruta_almacenamiento, existente.upload_id):
                        return JsonResponse({"error": "La limpieza anterior sigue pendiente.", "reintentable": True}, status=503)
                    eliminar_objeto(existente.ruta_almacenamiento)
            except RecursoOcupado:
                return JsonResponse({"error": "Este archivo se está verificando.", "reintentable": True}, status=409)
            except Exception:
                logger.error("No se pudo preparar el reintento de %s", existente.pk)
                return JsonResponse({"error": "No se pudo limpiar la carga anterior.", "reintentable": True}, status=503)
        upload_id = None
        inicio = monotonic()
        registrar_carga("archivo_inicio_solicitado", importacion_id=lote.pk, bytes_total=tamano, partes=partes)
        try:
            upload_id = iniciar_multipart_upload(clave, content_type)
            # Si falla la firma, la fila se revierte y la ruta queda disponible
            # para otro intento. S3 se compensa fuera de la transacción.
            with transaction.atomic():
                actual = ImportacionEstudio.objects.select_for_update().get(pk=lote.pk)
                if actual.estado != EstadoImportacion.CARGANDO:
                    raise ValidationError("La importación ya no admite cargas.")
                archivo = existente or Archivo(importacion=lote, nombre_archivo=nombre, ruta_relativa=ruta, formato=formato, categoria=categoria, tamano=tamano, content_type=content_type, cantidad_partes=partes)
                archivo.ruta_almacenamiento, archivo.upload_id = clave, upload_id
                archivo.estado, archivo.hash_sha256 = EstadoArchivo.CARGANDO, None
                archivo.save()
                urls = generar_urls_prefirmadas(clave, upload_id, partes)
            registrar_carga("archivo_carga_habilitada", importacion_id=lote.pk, archivo_id=archivo.pk,
                            bytes_total=tamano, partes=partes, duracion_ms=round((monotonic() - inicio) * 1000))
            return JsonResponse({"archivo_id": archivo.pk, "part_size": settings.S3_MULTIPART_PART_SIZE, "partes": urls, "carga_token": upload_id})
        except Exception as error:
            registrar_carga("archivo_inicio_error", importacion_id=lote.pk, error=error)
            logger.error("No se pudo iniciar archivo importado.")
            if upload_id and not abortar_multipart_upload(clave, upload_id):
                # Conservar la referencia si S3 no confirmó el aborto, para poder limpiarla.
                Archivo.objects.update_or_create(importacion=lote, ruta_relativa=ruta, defaults={
                    "nombre_archivo": nombre, "formato": formato, "categoria": categoria,
                    "ruta_almacenamiento": clave, "tamano": tamano, "upload_id": upload_id,
                    "content_type": content_type, "cantidad_partes": partes, "estado": EstadoArchivo.INCORRECTO})
            return JsonResponse({"error": "No se pudo iniciar la carga del archivo."}, status=502)


class CompletarArchivoImportadoView(AdminRequeridoMixin, View):
    @transferencia_exclusiva(lambda request, importacion_id, archivo_id: f"archivo:{archivo_id}")
    def post(self, request, importacion_id, archivo_id):
        archivo = get_object_or_404(Archivo, pk=archivo_id, importacion_id=importacion_id, importacion__iniciada_por=request.user)
        if archivo.estado == EstadoArchivo.COMPLETO:
            return JsonResponse({"status": "ok", "archivo_id": archivo.pk})
        data = _leer_json(request) or {}
        if archivo.estado != EstadoArchivo.CARGANDO or archivo.importacion.estado != EstadoImportacion.CARGANDO or data.get("carga_token") != archivo.upload_id:
            return JsonResponse({"error": "Esta carga ya no está vigente."}, status=409)
        partes = _partes_validas(data.get("partes"), archivo.cantidad_partes)
        if partes is None: return JsonResponse({"error": "La lista de partes es inválida."}, status=400)
        completo = False
        inicio = monotonic()
        registrar_carga("archivo_verificacion_iniciada", importacion_id=importacion_id, archivo_id=archivo.pk)
        try:
            resultado = completar_multipart_upload(archivo.ruta_almacenamiento, archivo.upload_id, partes); completo = True
            if resultado["tamano"] != archivo.tamano: raise ValueError("El tamaño recibido no coincide.")
            with transaction.atomic():
                actual = ImportacionEstudio.objects.select_for_update().get(pk=importacion_id)
                request.comprobar_bloqueo_transferencia()
                if actual.estado != EstadoImportacion.CARGANDO:
                    raise ValidationError("La importación fue cancelada.")
                archivo.estado = EstadoArchivo.COMPLETO; archivo.upload_id = None
                archivo.save(update_fields=["estado", "upload_id", "updated_at"])
            registrar_carga("archivo_completo", importacion_id=importacion_id, archivo_id=archivo.pk,
                            bytes_total=archivo.tamano, duracion_ms=round((monotonic() - inicio) * 1000))
            return JsonResponse({"status": "ok", "archivo_id": archivo.pk})
        except Exception as error:
            registrar_carga("archivo_verificacion_error", importacion_id=importacion_id, archivo_id=archivo.pk, error=error)
            logger.error("No se pudo completar archivo importado.")
            request.comprobar_bloqueo_transferencia()
            # La limpieza remota no debe ocultar el error de verificación ni
            # dejar un archivo fallido registrado como CARGANDO.
            upload_pendiente = None if completo else archivo.upload_id
            try:
                if completo:
                    eliminar_objeto(archivo.ruta_almacenamiento)
                elif abortar_multipart_upload(archivo.ruta_almacenamiento, archivo.upload_id):
                    upload_pendiente = None
            except Exception:
                logger.error("No se pudo limpiar el archivo importado %s.", archivo.pk)
            Archivo.objects.filter(pk=archivo.pk).update(
                estado=EstadoArchivo.INCORRECTO, upload_id=upload_pendiente,
            )
            return JsonResponse({"error": "No se pudo verificar el archivo."}, status=502)


class AnalizarImportacionView(AdminRequeridoMixin, View):
    def post(self, request, importacion_id):
        lote = get_object_or_404(ImportacionEstudio, pk=importacion_id, iniciada_por=request.user)
        try:
            lote = encolar(lote)
        except ValidationError as error:
            registrar_carga("analisis_rechazado", importacion_id=lote.pk, error=error)
            # Rechazar una transición no debe convertir una importación ya
            # confirmada en ERROR ni borrar su estado administrativo.
            return JsonResponse({"error": " ".join(error.messages)}, status=409)
        return JsonResponse({"status": "encolado", "estado": lote.estado,
            "estado_url": f"/estudios/importaciones/{lote.pk}/estado/",
            "detalle_url": f"/estudios/importaciones/{lote.pk}/"}, status=202)


class DetalleImportacionView(AdminRequeridoMixin, DetailView):
    model = ImportacionEstudio
    template_name = "estudios/importacion_detalle.html"
    context_object_name = "importacion"

    def get_queryset(self):
        return super().get_queryset().filter(iniciada_por=self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        
        derivante_id = self.request.GET.get('derivante')
        initial = {}
        if derivante_id:
            initial['derivante'] = derivante_id
            
        contexto["form"] = ConfirmarImportacionForm(importacion=self.object, initial=initial)
        contexto["mostrar_registro_paciente"] = not self.object.paciente_sugerido_id
        if not self.object.paciente_sugerido_id:
            contexto["paciente_form"] = RegistrarPacienteDetectadoForm(
                importacion=self.object
            )
        return contexto


class RegistrarPacienteDetectadoView(AdminRequeridoMixin, View):
    """Registra una ficha clínica y la selecciona para la importación actual."""

    @transaction.atomic
    def post(self, request, importacion_id):
        lote = get_object_or_404(
            ImportacionEstudio.objects.select_for_update(),
            pk=importacion_id,
            iniciada_por=request.user,
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
        )
        if lote.paciente_sugerido_id:
            messages.info(request, "La importación ya tiene un paciente seleccionado.")
            return redirect("importacion_detalle", pk=lote.pk)

        dni_ingresado = request.POST.get("dni", "").strip()
        if lote.pacientes_mezclados:
            return JsonResponse({"error": "La carpeta contiene identidades incompatibles. Separá los pacientes antes de cargarla."}, status=409)
        if dni_ingresado:
            paciente_existente = Paciente.objects.filter(dni=dni_ingresado).first()
            if paciente_existente:
                with transaction.atomic():
                    lote.paciente_sugerido = paciente_existente
                    lote.save(update_fields=["paciente_sugerido", "updated_at"])
                messages.info(
                    request,
                    f"El DNI {dni_ingresado} pertenece a {paciente_existente}. Verificá los datos y confirmá el estudio."
                )
                return redirect("importacion_detalle", pk=lote.pk)

        form = RegistrarPacienteDetectadoForm(request.POST, importacion=lote)
        if form.is_valid():
            with transaction.atomic():
                try:
                    with transaction.atomic():
                        paciente = form.save()
                except IntegrityError:
                    # Otro registro concurrente pudo crear este DNI después de validar.
                    paciente = Paciente.objects.filter(dni=form.cleaned_data["dni"]).first()
                    if paciente is None:
                        raise
                lote.paciente_sugerido = paciente
                lote.save(update_fields=["paciente_sugerido", "updated_at"])
            messages.success(
                request,
                f"La ficha de {paciente} fue creada y quedó seleccionada para este estudio.",
            )
            return redirect("importacion_detalle", pk=lote.pk)

        return render(
            request,
            "estudios/importacion_detalle.html",
            {
                "importacion": lote,
                "form": ConfirmarImportacionForm(importacion=lote),
                "paciente_form": form,
                "mostrar_registro_paciente": True,
            },
        )


class ConfirmarImportacionView(AdminRequeridoMixin, View):
    def post(self, request, importacion_id):
        # Adquirir el bloqueo antes de crear Estudio evita duplicados ante dos
        # POST que hayan observado el mismo lote pendiente.
        with transaction.atomic():
            lote = get_object_or_404(
                ImportacionEstudio.objects.select_for_update(),
                pk=importacion_id,
                iniciada_por=request.user,
            )
            if lote.estudio_id or lote.estado != EstadoImportacion.PENDIENTE_CONFIRMACION:
                return JsonResponse(
                    {"error": "La importación no está pendiente de confirmación."},
                    status=409,
                )
            if not lote.esta_completa() or lote.archivos.filter(estudio__isnull=False).exists():
                return JsonResponse({"error": "Los archivos no están disponibles para confirmar."}, status=409)
            if lote.pacientes_mezclados:
                return JsonResponse({"error": "La carpeta contiene identidades incompatibles. Cargá una carpeta por paciente."}, status=409)
            form = ConfirmarImportacionForm(request.POST, importacion=lote)
            if not form.is_valid():
                contexto = {
                    "importacion": lote,
                    "form": form,
                    "mostrar_registro_paciente": not lote.paciente_sugerido_id,
                }
                if not lote.paciente_sugerido_id:
                    contexto["paciente_form"] = RegistrarPacienteDetectadoForm(importacion=lote)
                return render(request, "estudios/importacion_detalle.html", contexto)
            estudio = form.save()
            lote.confirmar(estudio, estudios_revisados=form.cleaned_data["estudios_revisados"])
            transaction.on_commit(lambda: registrar_carga("importacion_confirmada", importacion_id=lote.pk, estudio_id=estudio.pk))
            derivante = form.cleaned_data.get("derivante")
            if derivante:
                Autorizacion.objects.create(
                    estudio=estudio,
                    odontologo=derivante,
                )
                try:
                    estudio.publicar()
                except ValidationError:
                    pass
            LogActividad.objects.create(usuario=request.user, estudio=estudio, tipo_evento=TipoEvento.IMPORTACION_CONFIRMADA, resultado="Estudio creado desde importación", detalles=f"Importación {lote.pk} confirmada. Revisión de estudios distintos: {lote.requiere_revision_estudios}.")
        if derivante:
            messages.success(
                request,
                f"La carpeta fue confirmada y el estudio quedó asociado a {derivante}.",
            )
        else:
            messages.success(
                request,
                "La carpeta fue confirmada y el estudio quedó guardado como borrador sin odontólogo derivante.",
            )
        return redirect("estudio_detalle", pk=estudio.pk)


class EliminarEstudioView(AdminRequeridoMixin, View):
    """Realiza una baja lógica y conserva todos los metadatos y objetos."""

    def post(self, request, pk):
        motivo = request.POST.get("motivo", "").strip()
        if not motivo:
            messages.error(request, "Indicá el motivo de la eliminación.")
            return redirect("estudio_detalle", pk=pk)

        with transaction.atomic():
            estudio = get_object_or_404(
                Estudio.objects.select_for_update().exclude(
                    estado=EstadoEstudio.ELIMINADO
                ),
                pk=pk,
            )
            autorizaciones = estudio.autorizaciones.select_for_update().filter(
                estado_acceso=EstadoAcceso.VIGENTE
            )
            revocadas = 0
            for autorizacion in autorizaciones:
                autorizacion.revocar(request.user)
                revocadas += 1
            estudio.eliminar_logicamente(request.user, motivo)
            LogActividad.objects.create(
                usuario=request.user,
                estudio=estudio,
                tipo_evento=TipoEvento.ELIMINACION,
                resultado="Estudio eliminado lógicamente",
                detalles=(
                    f"Motivo: {motivo}. Accesos revocados: {revocadas}. "
                    "Los archivos físicos se conservaron."
                ),
            )

        messages.success(
            request,
            "El estudio fue eliminado lógicamente y todavía puede auditarse.",
        )
        return redirect("estudio_detalle", pk=estudio.pk)


class PurgarEstudioView(AdminRequeridoMixin, View):
    """Borra los objetos físicos de un estudio eliminado, conservando su ficha."""

    def post(self, request, pk):
        estudio = get_object_or_404(
            Estudio.objects.filter(estado=EstadoEstudio.ELIMINADO),
            pk=pk,
        )
        confirmacion_esperada = f"ELIMINAR ESTUDIO {estudio.pk}"
        if request.POST.get("confirmacion", "").strip() != confirmacion_esperada:
            messages.error(
                request,
                f"Para purgar los archivos escribí exactamente: {confirmacion_esperada}",
            )
            return redirect("estudio_detalle", pk=estudio.pk)

        purgados = 0
        errores = []
        archivos = estudio.archivos.exclude(estado=EstadoArchivo.PURGADO).order_by("pk")
        for archivo in archivos:
            try:
                if archivo.upload_id:
                    if not abortar_multipart_upload(
                        archivo.ruta_almacenamiento,
                        archivo.upload_id,
                    ):
                        raise RuntimeError("MinIO no confirmó la cancelación multipartes.")
                else:
                    eliminar_objeto(archivo.ruta_almacenamiento)
            except Exception:
                logger.error(
                    "No se pudo purgar el objeto del archivo %s.", archivo.pk
                )
                errores.append(archivo.pk)
                continue

            archivo.estado = EstadoArchivo.PURGADO
            archivo.upload_id = None
            archivo.save(update_fields=["estado", "upload_id", "updated_at"])
            purgados += 1

        LogActividad.objects.create(
            usuario=request.user,
            estudio=estudio,
            tipo_evento=TipoEvento.ELIMINACION,
            resultado="Purga física solicitada",
            detalles=(
                f"Objetos purgados: {purgados}. "
                f"Errores pendientes: {errores or 'ninguno'}. "
                "Se conservaron metadatos, hashes y relaciones de reemplazo."
            ),
        )
        if errores:
            messages.error(
                request,
                f"Se purgaron {purgados} archivos, pero {len(errores)} deberán reintentarse.",
            )
        else:
            messages.success(
                request,
                f"Se eliminaron definitivamente {purgados} archivos de MinIO. La trazabilidad se conservó.",
            )
        return redirect("estudio_detalle", pk=estudio.pk)


class VerEstudioView(EstudioAccesoMixin, DetailView):
    """Vista de archivos para el odontólogo y el paciente."""

    model = Estudio
    template_name = "estudios/estudio_ver.html"
    context_object_name = "estudio"

    def get_queryset(self):
        return Estudio.objects.select_related("paciente")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        archivos = self.object.archivos.filter(estado=EstadoArchivo.COMPLETO).order_by(
            "ruta_relativa", "nombre_archivo", "pk",
        )
        contexto.update(contexto_archivos(archivos, self.request.GET.get("archivos_pagina")))
        return contexto


class DescargarEstudioCompletoView(EstudioAccesoMixin, SingleObjectMixin, View):
    """Permite descargar la carpeta completa (raíz) del estudio en un archivo ZIP.
    Disponible para Administradores, Odontólogos con autorización vigente y Pacientes titulares.
    """

    model = Estudio

    @transferencia_exclusiva(lambda request, **kwargs: "preparacion-zip")
    def get(self, request, *args, **kwargs):
        estudio = self.get_object()

        archivos = estudio.archivos.filter(
            estado=EstadoArchivo.COMPLETO,
        ).order_by("ruta_relativa", "nombre_archivo")

        if not archivos.exists():
            messages.error(request, "El estudio no contiene archivos disponibles para descargar.")
            return redirect("estudio_ver", pk=estudio.pk)

        temp_file = None
        s3 = None
        try:
            # Un solo armado por base de datos (entre procesos del VPS). Los
            # ZIP ya preparados siguen descargándose sin retener este bloqueo.
            resumen = archivos.aggregate(total=Sum("tamano"), cantidad=Count("pk"))
            total, cantidad_archivos = resumen["total"] or 0, resumen["cantidad"]
            if total > settings.ZIP_MAX_TAMANO_TOTAL or cantidad_archivos > settings.ZIP_MAX_ARCHIVOS:
                return JsonResponse({"error": "El estudio supera el límite de preparación ZIP. Descargá sus archivos individualmente o consultá al centro."}, status=413)
            directorio = settings.ZIP_TEMP_DIR or tempfile.gettempdir()
            # DEFLATE puede expandir datos ya comprimidos: margen conservador
            # más cabeceras por entrada; no promete sustituir una cuota de disco.
            necesarios = total + total // 100 + cantidad_archivos * 65536 + settings.ZIP_RESERVA_DISCO
            if shutil.disk_usage(directorio).free < necesarios:
                return JsonResponse({"error": "No hay espacio temporal suficiente para preparar la descarga. Avisá al centro."}, status=507)
            s3 = get_s3_client()
            temp_file = tempfile.TemporaryFile(dir=directorio)
            nombres = set()
            cantidad = 0
            with zipfile.ZipFile(temp_file, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
                for archivo in archivos.iterator(chunk_size=100):
                    arcname = _ruta_importada_valida(archivo.ruta_relativa or archivo.nombre_archivo)
                    if not arcname or arcname in nombres:
                        raise ValueError("El estudio contiene rutas de descarga inválidas o repetidas.")
                    nombres.add(arcname)
                    obj = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=archivo.ruta_almacenamiento)
                    cuerpo = obj["Body"]
                    try:
                        escritos = 0
                        # Zip64 permite entradas grandes. Leer por bloques evita
                        # cargar una tomografía completa en RAM.
                        with zf.open(arcname, mode="w", force_zip64=True) as destino:
                            while bloque := cuerpo.read(ZIP_CHUNK_SIZE):
                                escritos += len(bloque)
                                if escritos > archivo.tamano:
                                    raise ValueError("El tamaño almacenado no coincide con el archivo.")
                                destino.write(bloque)
                        if escritos != archivo.tamano:
                            raise ValueError("El archivo almacenado está incompleto.")
                    finally:
                        cuerpo.close()
                    cantidad += 1

            temp_file.seek(0)
            paciente_str = f"{estudio.paciente.apellido}_{estudio.paciente.nombre}".replace(" ", "_")
            nombre_zip = f"Estudio_{paciente_str}_{estudio.pk}.zip"
            nombre_zip = "".join(c for c in nombre_zip if c.isalnum() or c in "._-")
            LogActividad.objects.create(
                usuario=request.user,
                estudio=estudio,
                tipo_evento=TipoEvento.DESCARGA,
                resultado="Paquete ZIP preparado",
                detalles=f"Descarga de carpeta raíz del estudio #{estudio.pk} ({cantidad} archivos).",
            )
            # FileResponse se encarga de cerrar el temporal al terminar o
            # interrumpirse la respuesta, sin mantener el ZIP en memoria.
            return FileResponse(temp_file, as_attachment=True, filename=nombre_zip, content_type="application/zip")
        except Exception:
            if temp_file is not None:
                temp_file.close()
            logger.error("No se pudo preparar el ZIP del estudio %s.", estudio.pk)
            LogActividad.objects.create(
                usuario=request.user,
                estudio=estudio,
                tipo_evento=TipoEvento.DESCARGA,
                resultado="Error al preparar paquete ZIP",
                detalles=f"No se entregó un paquete parcial del estudio #{estudio.pk}.",
            )
            return JsonResponse(
                {"error": "No se pudo preparar la descarga completa. Intentá nuevamente o avisá al centro."},
                status=502,
            )
        finally:
            if s3 is not None:
                s3.close()

