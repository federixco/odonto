import json
import logging
import math
import uuid
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.archivos.models import Archivo
from apps.archivos.services.storage import (
    abortar_multipart_upload,
    calcular_sha256_objeto,
    completar_multipart_upload,
    eliminar_objeto,
    generar_urls_prefirmadas,
    iniciar_multipart_upload,
)
from apps.auditoria.models import LogActividad
from apps.core.enums import CategoriaArchivo, EstadoArchivo, EstadoEstudio, EstadoImportacion, FormatoArchivo, TipoEvento
from apps.core.mixins import AdminRequeridoMixin
from .forms import (
    ConfirmarImportacionForm,
    EstudioForm,
    RegistrarPacienteDetectadoForm,
)
from .models import Estudio, ImportacionEstudio
from .services.importador import analizar_importacion


logger = logging.getLogger(__name__)
S3_MIN_PART_SIZE = 5 * 1024 * 1024
S3_MAX_PARTS = 10_000


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
        if not isinstance(parte, dict) or not isinstance(parte.get("PartNumber"), int) or not isinstance(parte.get("ETag"), str):
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
    """Listado de todos los estudios con búsqueda y filtro por estado."""

    model = Estudio
    template_name = "estudios/estudio_lista.html"
    context_object_name = "estudios"

    def get_queryset(self):
        queryset = Estudio.objects.select_related("paciente").order_by(
            "-fecha_estudio", "-created_at"
        )
        busqueda = self.request.GET.get("q", "").strip()
        if busqueda:
            queryset = queryset.filter(
                Q(paciente__nombre__icontains=busqueda)
                | Q(paciente__apellido__icontains=busqueda)
                | Q(paciente__dni__icontains=busqueda)
                | Q(tipo__icontains=busqueda)
            )
        estado = self.request.GET.get("estado", "").strip()
        if estado and estado in EstadoEstudio.values:
            queryset = queryset.filter(estado=estado)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["busqueda"] = self.request.GET.get("q", "")
        contexto["estado_filtro"] = self.request.GET.get("estado", "")
        contexto["estados"] = EstadoEstudio.choices
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
    """Muestra el estudio en preparación y coordina la carga de sus archivos."""
    model = Estudio
    template_name = "estudios/estudio_detalle.html"
    context_object_name = "estudio"


class CrearImportacionView(AdminRequeridoMixin, View):
    """Pantalla para seleccionar una carpeta exportada por el equipo clínico."""

    def get(self, request):
        return render(request, "estudios/importacion_crear.html")


class IniciarImportacionView(AdminRequeridoMixin, View):
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
        lote = ImportacionEstudio.objects.create(iniciada_por=request.user, nombre_carpeta=nombre.strip(), cantidad_archivos=cantidad, tamano_total=tamano)
        LogActividad.objects.create(usuario=request.user, tipo_evento=TipoEvento.IMPORTACION_INICIADA, resultado="Importación iniciada", detalles=f"Importación {lote.pk}: {cantidad} archivos, {tamano} bytes.")
        return JsonResponse({"importacion_id": lote.pk, "detalle_url": f"/estudios/importaciones/{lote.pk}/"})


class IniciarArchivoImportadoView(AdminRequeridoMixin, View):
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
        extension, formato, categoria, content_type = _clasificar_importado(nombre)
        partes = math.ceil(tamano / settings.S3_MULTIPART_PART_SIZE)
        if partes > S3_MAX_PARTS: return JsonResponse({"error": "El archivo requiere demasiadas partes."}, status=400)
        clave = f"importaciones/{lote.pk}/archivos/{uuid.uuid4().hex}{extension}"
        upload_id = None
        try:
            upload_id = iniciar_multipart_upload(clave, content_type)
            archivo = Archivo.objects.create(importacion=lote, nombre_archivo=nombre, ruta_relativa=ruta, formato=formato, categoria=categoria, ruta_almacenamiento=clave, tamano=tamano, upload_id=upload_id, content_type=content_type, cantidad_partes=partes)
            return JsonResponse({"archivo_id": archivo.pk, "part_size": settings.S3_MULTIPART_PART_SIZE, "partes": generar_urls_prefirmadas(clave, upload_id, partes)})
        except Exception:
            logger.exception("No se pudo iniciar archivo importado.")
            if upload_id: abortar_multipart_upload(clave, upload_id)
            return JsonResponse({"error": "No se pudo iniciar la carga del archivo."}, status=502)


class CompletarArchivoImportadoView(AdminRequeridoMixin, View):
    def post(self, request, importacion_id, archivo_id):
        archivo = get_object_or_404(Archivo, pk=archivo_id, importacion_id=importacion_id, importacion__iniciada_por=request.user, estado=EstadoArchivo.CARGANDO)
        partes = _partes_validas((_leer_json(request) or {}).get("partes"), archivo.cantidad_partes)
        if partes is None: return JsonResponse({"error": "La lista de partes es inválida."}, status=400)
        completo = False
        try:
            resultado = completar_multipart_upload(archivo.ruta_almacenamiento, archivo.upload_id, partes); completo = True
            if resultado["tamano"] != archivo.tamano: raise ValueError("El tamaño recibido no coincide.")
            archivo.hash_sha256 = calcular_sha256_objeto(archivo.ruta_almacenamiento)
            archivo.estado = EstadoArchivo.COMPLETO; archivo.upload_id = None
            archivo.save(update_fields=["hash_sha256", "estado", "upload_id", "updated_at"])
            return JsonResponse({"status": "ok", "archivo_id": archivo.pk})
        except Exception:
            logger.exception("No se pudo completar archivo importado.")
            if completo: eliminar_objeto(archivo.ruta_almacenamiento)
            else: abortar_multipart_upload(archivo.ruta_almacenamiento, archivo.upload_id)
            Archivo.objects.filter(pk=archivo.pk).update(estado=EstadoArchivo.INCORRECTO, upload_id=None)
            return JsonResponse({"error": "No se pudo verificar el archivo."}, status=502)


class AnalizarImportacionView(AdminRequeridoMixin, View):
    def post(self, request, importacion_id):
        lote = get_object_or_404(ImportacionEstudio, pk=importacion_id, iniciada_por=request.user)
        try:
            lote.marcar_procesando()
            lote = analizar_importacion(lote)
            return JsonResponse({"status": "ok", "detalle_url": f"/estudios/importaciones/{lote.pk}/"})
        except Exception as error:
            logger.exception("No se pudo analizar importación %s.", lote.pk)
            lote.marcar_error(error)
            return JsonResponse({"error": "No se pudo analizar la carpeta. Revisá los archivos o intentá nuevamente."}, status=422)


class DetalleImportacionView(AdminRequeridoMixin, DetailView):
    model = ImportacionEstudio
    template_name = "estudios/importacion_detalle.html"
    context_object_name = "importacion"

    def get_queryset(self):
        return super().get_queryset().filter(iniciada_por=self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["form"] = ConfirmarImportacionForm(importacion=self.object)
        contexto["mostrar_registro_paciente"] = (
            self.request.GET.get("registrar_paciente") == "1"
            and not self.object.paciente_sugerido_id
        )
        if contexto["mostrar_registro_paciente"]:
            contexto["paciente_form"] = RegistrarPacienteDetectadoForm(
                importacion=self.object
            )
        return contexto


class RegistrarPacienteDetectadoView(AdminRequeridoMixin, View):
    """Registra una ficha clínica y la selecciona para la importación actual."""

    def post(self, request, importacion_id):
        lote = get_object_or_404(
            ImportacionEstudio,
            pk=importacion_id,
            iniciada_por=request.user,
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
        )
        if lote.paciente_sugerido_id:
            messages.info(request, "La importación ya tiene un paciente seleccionado.")
            return redirect("importacion_detalle", pk=lote.pk)

        form = RegistrarPacienteDetectadoForm(request.POST, importacion=lote)
        if form.is_valid():
            with transaction.atomic():
                paciente = form.save()
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
        lote = get_object_or_404(ImportacionEstudio, pk=importacion_id, iniciada_por=request.user, estado=EstadoImportacion.PENDIENTE_CONFIRMACION)
        form = ConfirmarImportacionForm(request.POST, importacion=lote)
        if not form.is_valid():
            return render(request, "estudios/importacion_detalle.html", {"importacion": lote, "form": form})
        with transaction.atomic():
            estudio = form.save()
            lote.confirmar(estudio)
            LogActividad.objects.create(usuario=request.user, estudio=estudio, tipo_evento=TipoEvento.IMPORTACION_CONFIRMADA, resultado="Estudio creado desde importación", detalles=f"Importación {lote.pk} confirmada.")
        messages.success(request, "La carpeta fue confirmada y el estudio quedó creado en borrador.")
        return redirect("estudio_detalle", pk=estudio.pk)
