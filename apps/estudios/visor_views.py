"""Acceso privado al visor; los bytes viajan S3 → navegador, no por Django."""
import json
from functools import wraps
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.archivos.models import Archivo
from apps.archivos.services.storage import generar_url_previsualizacion
from apps.auditoria.models import LogActividad
from apps.core.enums import EstadoArchivo, RolUsuario, TipoEvento
from apps.core.permisos_estudios import comprobar_acceso_estudio
from .models import Estudio
from .services.visor import archivos_disponibles, solicitar

SALT = "doc.visor.apertura.v1"


def privado(view):
    @wraps(view)
    def wrapper(request, pk, *args, **kwargs):
        # También en los JSON: jamás redirigir un decoder hacia el HTML del login.
        if not request.user.is_authenticated:
            response = JsonResponse({"error": "La sesión terminó. Volvé a ingresar."}, status=401)
        else:
            try:
                estudio = get_object_or_404(Estudio.objects.select_related("paciente"), pk=pk)
                comprobar_acceso_estudio(request.user, estudio)
                response = view(request, estudio, *args, **kwargs)
            except PermissionDenied:
                response = JsonResponse({"error": "No tenés acceso a este estudio."}, status=403)
            except Http404:
                response = JsonResponse({"error": "Contenido no disponible."}, status=404)
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Content-Type-Options"] = "nosniff"
        response["Vary"] = "Cookie"
        return response
    return wrapper


def limites():
    return {"meshBytes": settings.VISOR_MAX_MESH_BYTES, "vertices": settings.VISOR_MAX_VERTICES,
            "imageBytes": settings.VISOR_MAX_IMAGE_BYTES, "volumeBytes": settings.VISOR_MAX_VOLUME_BYTES,
            "frames": settings.VISOR_MAX_FRAMES, "concurrency": min(4, settings.VISOR_CONCURRENCY)}


@require_GET
@privado
def pagina(request, estudio):
    token = signing.dumps({"usuario": request.user.pk, "estudio": estudio.pk, "nonce": uuid4().hex}, salt=SALT)
    LogActividad.objects.create(usuario=request.user, estudio=estudio, tipo_evento=TipoEvento.VISUALIZACION,
                                resultado="Visor solicitado", detalles="Apertura de visor; no confirma renderizado.")
    config = {"catalogo": reverse("visor_catalogo", args=[estudio.pk]),
              "eventos": reverse("visor_eventos", args=[estudio.pk]), "token": token, "limites": limites()}
    volver = reverse("estudio_detalle" if request.user.rol == RolUsuario.ADMINISTRADOR else "estudio_ver", args=[estudio.pk])
    return render(request, "estudios/visor.html", {"estudio": estudio, "visor_config": config, "volver": volver})


@require_http_methods(["GET", "POST"])
@privado
def catalogo(request, estudio):
    archivos = archivos_disponibles(estudio)
    modelos = [{"id": a.pk, "nombre": a.nombre_archivo, "formato": a.formato, "bytes": a.tamano,
                "disponible": a.tamano <= settings.VISOR_MAX_MESH_BYTES,
                "url": reverse("visor_contenido", args=[estudio.pk, a.pk])}
               for a in archivos.filter(formato__in=["STL", "PLY"])]
    if archivos.exclude(formato__in=["STL", "PLY", "JPG", "PNG", "TIFF", "PDF"]).exists():
        indice = solicitar(estudio, reintentar=request.method == "POST")
    else:
        indice = {"estado": "listo", "series": [], "omitidos": []}
    series = [{"id": s["id"], "nombre": f"Serie {n+1}", "frames": s["frames"],
               "volumen": s["volumen"], "motivo": s["motivo"],
               "url": reverse("visor_serie", args=[estudio.pk, s["id"]])}
              for n, s in enumerate(indice["series"])]
    # El enlace de un archivo abre su serie, sin mandar todos sus IDs al catálogo.
    archivo_solicitado = request.GET.get("archivo", "")
    seleccion = next((f"m-{m['id']}" for m in modelos
                      if str(m["id"]) == archivo_solicitado and m["disponible"]), None)
    if seleccion is None:
        seleccion = next((f"s-{s['id']}" for s in indice["series"]
                          if any(str(a["archivo"]) == archivo_solicitado for a in s["archivos"])), None)
    return JsonResponse({"estado": indice["estado"], "modelos": modelos, "series": series,
                         "seleccion": seleccion, "omitidos": indice["omitidos"]},
                        status=202 if indice["estado"] == "preparando" else 200)


@require_GET
@privado
def serie(request, estudio, serie_id):
    indice = solicitar(estudio)
    if indice["estado"] != "listo":
        return JsonResponse({"error": "El índice no está disponible. Actualizá el catálogo."}, status=409)
    seleccionada = next((s for s in indice["series"] if s["id"] == serie_id), None)
    if not seleccionada:
        raise Http404()
    return JsonResponse({"id": seleccionada["id"], "frames": seleccionada["frames"],
                         "volumen": seleccionada["volumen"], "motivo": seleccionada["motivo"],
                         "memoria_estimada": seleccionada["memoria_estimada"],
                         "archivos": [{"id": a["archivo"], "frames": a["frames"], "bytes": a["bytes"],
                                       "url": reverse("visor_contenido", args=[estudio.pk, a["archivo"]])}
                                      for a in seleccionada["archivos"]]})


@require_GET
@privado
def contenido(request, estudio, archivo_id):
    archivo = get_object_or_404(Archivo, pk=archivo_id, estudio=estudio, estado=EstadoArchivo.COMPLETO)
    # No firmar cualquier XML/EXE del paquete aunque esté etiquetado DICOM.
    if archivo.formato in {"STL", "PLY"}:
        if archivo.tamano > settings.VISOR_MAX_MESH_BYTES:
            return JsonResponse({"error": "Modelo demasiado grande para el visor."}, status=413)
    else:
        indice = solicitar(estudio)
        if not any(a["archivo"] == archivo.pk for s in indice["series"] for a in s["archivos"]):
            raise Http404("Objeto no compatible con el visor.")
    try:
        url = generar_url_previsualizacion(archivo.ruta_almacenamiento, content_type="application/octet-stream")
    except Exception:
        return JsonResponse({"error": "No se pudo autorizar la lectura. Reintentá."}, status=503)
    return HttpResponseRedirect(url)


@require_POST
@privado
def eventos(request, estudio):
    """Un resultado por apertura, serializado en DB; nunca logs por frame/cámara."""
    if len(request.body) > 2048:
        return JsonResponse({"error": "Evento demasiado grande."}, status=400)
    try:
        data = json.loads(request.body)
        token = signing.loads(data["token"], salt=SALT, max_age=3600)
        if (token["usuario"] != request.user.pk or token["estudio"] != estudio.pk
                or data["resultado"] not in {"renderizado", "fallo"}
                or data["modo"] not in {"modelo", "cortes", "volumen"}
                or data.get("codigo", "") not in {"", "red", "memoria", "formato", "webgl", "cancelado", "desconocido"}):
            raise ValueError()
    except (ValueError, TypeError, KeyError, AssertionError, signing.BadSignature):
        return JsonResponse({"error": "Evento inválido o vencido."}, status=400)
    identificador = f"visor:{token['nonce']} "
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        existe = LogActividad.objects.filter(usuario=request.user, estudio=estudio,
                    tipo_evento=TipoEvento.VISUALIZACION, detalles__startswith=identificador).exists()
        if not existe:
            LogActividad.objects.create(usuario=request.user, estudio=estudio, tipo_evento=TipoEvento.VISUALIZACION,
                resultado=f"Cliente reporta {data['resultado']}",
                detalles=f"{identificador}modo={data['modo']} codigo={data.get('codigo', '')}; reporte no certifica lectura clínica.")
    return JsonResponse({"registrado": True})
