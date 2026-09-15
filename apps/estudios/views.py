import json
import logging
import math
import uuid
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
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
from apps.accesos.models import Autorizacion
from apps.auditoria.models import LogActividad
from apps.core.enums import CategoriaArchivo, EstadoAcceso, EstadoArchivo, EstadoEstudio, EstadoImportacion, FormatoArchivo, TipoEvento
from apps.core.mixins import AdminRequeridoMixin, EstudioAccesoMixin
from apps.usuarios.models import Odontologo
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
    """Resume el estudio, sus archivos y los profesionales con acceso."""

    model = Estudio
    template_name = "estudios/estudio_detalle.html"
    context_object_name = "estudio"

    def get_queryset(self):
        return Estudio.objects.select_related("paciente")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        archivos = self.object.archivos.order_by("ruta_relativa", "nombre_archivo")
        contexto["archivos_pagina"] = Paginator(archivos, 100).get_page(
            self.request.GET.get("archivos_pagina")
        )

        autorizaciones = self.object.autorizaciones.select_related(
            "odontologo__usuario",
            "revocado_por",
        ).order_by("odontologo__apellido", "odontologo__nombre")
        contexto["accesos_vigentes"] = autorizaciones.filter(
            estado_acceso=EstadoAcceso.VIGENTE
        )
        contexto["accesos_revocados"] = autorizaciones.filter(
            estado_acceso=EstadoAcceso.REVOCADO
        )
        odontologos_asociados = autorizaciones.values_list(
            "odontologo_id", flat=True
        )
        contexto["odontologos_disponibles"] = (
            Odontologo.objects.select_related("usuario")
            .exclude(pk__in=odontologos_asociados)
            .order_by("apellido", "nombre", "matricula")
        )

        # --- Construcción del árbol (agregado) ---
        archivos_list = list(archivos)
        contexto["total_archivos"] = len(archivos_list)
        if not archivos_list:
            contexto["tree"] = None
        else:
            tree = {"nombre": "Raíz", "archivos": [], "subcarpetas": {}, "tamano_total": 0, "total_archivos_recursivo": 0}
            for archivo in archivos_list:
                partes = archivo.ruta_relativa.split("/") if archivo.ruta_relativa else []
                if partes and partes[-1] == archivo.nombre_archivo:
                    partes_carpeta = partes[:-1]
                else:
                    partes_carpeta = partes

                current = tree
                current["tamano_total"] += archivo.tamano
                current["total_archivos_recursivo"] += 1
                
                for parte in partes_carpeta:
                    if parte not in current["subcarpetas"]:
                        current["subcarpetas"][parte] = {
                            "nombre": parte, 
                            "archivos": [], 
                            "subcarpetas": {}, 
                            "tamano_total": 0,
                            "total_archivos_recursivo": 0
                        }
                    current = current["subcarpetas"][parte]
                    current["tamano_total"] += archivo.tamano
                    current["total_archivos_recursivo"] += 1
                    
                current["archivos"].append(archivo)

            while not tree["archivos"] and len(tree["subcarpetas"]) == 1:
                unica_llave = list(tree["subcarpetas"].keys())[0]
                tree = tree["subcarpetas"][unica_llave]

            contexto["tree"] = tree
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
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION
        ).order_by("-created_at")
        
        return render(
            request,
            "estudios/importacion_crear.html",
            {
                "estudios_recientes": estudios_recientes,
                "pendientes": pendientes,
            },
        )


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
        contexto["mostrar_registro_paciente"] = not self.object.paciente_sugerido_id
        if not self.object.paciente_sugerido_id:
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
            contexto = {
                "importacion": lote,
                "form": form,
                "mostrar_registro_paciente": not lote.paciente_sugerido_id,
            }
            if not lote.paciente_sugerido_id:
                contexto["paciente_form"] = RegistrarPacienteDetectadoForm(
                    importacion=lote
                )
            return render(request, "estudios/importacion_detalle.html", contexto)
        with transaction.atomic():
            estudio = form.save()
            lote.confirmar(estudio)
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
            LogActividad.objects.create(usuario=request.user, estudio=estudio, tipo_evento=TipoEvento.IMPORTACION_CONFIRMADA, resultado="Estudio creado desde importación", detalles=f"Importación {lote.pk} confirmada.")
        messages.success(
            request,
            f"La carpeta fue confirmada y el estudio quedó asociado a {derivante}.",
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
        archivos = self.object.archivos.order_by("ruta_relativa", "nombre_archivo")
        
        archivos_list = list(archivos)
        contexto["total_archivos"] = len(archivos_list)
        if not archivos_list:
            contexto["tree"] = None
        else:
            tree = {"nombre": "Raíz", "archivos": [], "subcarpetas": {}, "tamano_total": 0, "total_archivos_recursivo": 0}
            for archivo in archivos_list:
                partes = archivo.ruta_relativa.split("/") if archivo.ruta_relativa else []
                if partes and partes[-1] == archivo.nombre_archivo:
                    partes_carpeta = partes[:-1]
                else:
                    partes_carpeta = partes

                current = tree
                current["tamano_total"] += archivo.tamano
                current["total_archivos_recursivo"] += 1
                
                for parte in partes_carpeta:
                    if parte not in current["subcarpetas"]:
                        current["subcarpetas"][parte] = {
                            "nombre": parte, 
                            "archivos": [], 
                            "subcarpetas": {}, 
                            "tamano_total": 0,
                            "total_archivos_recursivo": 0
                        }
                    current = current["subcarpetas"][parte]
                    current["tamano_total"] += archivo.tamano
                    current["total_archivos_recursivo"] += 1
                    
                current["archivos"].append(archivo)

            while not tree["archivos"] and len(tree["subcarpetas"]) == 1:
                unica_llave = list(tree["subcarpetas"].keys())[0]
                tree = tree["subcarpetas"][unica_llave]

            contexto["tree"] = tree
            
        return contexto
