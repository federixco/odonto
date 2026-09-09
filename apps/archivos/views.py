import json
import uuid
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from apps.core.mixins import AdminRequeridoMixin
from apps.estudios.models import Estudio
from apps.core.enums import EstadoArchivo, CategoriaArchivo, FormatoArchivo
from .models import Archivo
from .services.storage import (
    iniciar_multipart_upload,
    generar_urls_prefirmadas,
    completar_multipart_upload,
    abortar_multipart_upload
)

class IniciarArchivoView(AdminRequeridoMixin, View):
    """Inicia la carga de un archivo para un estudio."""
    
    def post(self, request, estudio_id):
        estudio = get_object_or_404(Estudio, pk=estudio_id)
        
        try:
            data = json.loads(request.body)
            nombre_archivo = data.get("nombre_archivo")
            formato = data.get("formato")
            categoria = data.get("categoria", CategoriaArchivo.IMAGEN_DOCUMENTO)
            tamano = int(data.get("tamano", 0))
            cantidad_partes = int(data.get("cantidad_partes", 1))
            content_type = data.get("content_type", "application/octet-stream")
        except (ValueError, json.JSONDecodeError):
            return JsonResponse({"error": "Datos inválidos"}, status=400)
            
        if not nombre_archivo or not formato or not tamano:
            return JsonResponse({"error": "Faltan datos obligatorios"}, status=400)

        # Generar clave única y segura (sin PII)
        clave_objeto = f"estudios/{estudio.pk}/archivos/{uuid.uuid4()}/{nombre_archivo}"
        
        # 1. Iniciar en S3
        try:
            upload_id = iniciar_multipart_upload(clave_objeto, content_type)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
            
        # 2. Registrar en DB como CARGANDO
        archivo = Archivo.objects.create(
            estudio=estudio,
            nombre_archivo=nombre_archivo,
            formato=formato,
            categoria=categoria,
            ruta_almacenamiento=clave_objeto,
            tamano=tamano,
            upload_id=upload_id,
            content_type=content_type,
            cantidad_partes=cantidad_partes,
            estado=EstadoArchivo.CARGANDO
        )
        
        # 3. Generar URLs prefirmadas
        try:
            urls = generar_urls_prefirmadas(clave_objeto, upload_id, cantidad_partes)
        except Exception as e:
            archivo.estado = EstadoArchivo.INCORRECTO
            archivo.save()
            return JsonResponse({"error": str(e)}, status=500)
            
        return JsonResponse({
            "archivo_id": archivo.pk,
            "upload_id": upload_id,
            "clave_objeto": clave_objeto,
            "partes": urls
        })


class CompletarArchivoView(AdminRequeridoMixin, View):
    """Recibe los ETags y completa la carga multipartes."""
    
    def post(self, request, archivo_id):
        archivo = get_object_or_404(Archivo, pk=archivo_id, estado=EstadoArchivo.CARGANDO)
        
        try:
            data = json.loads(request.body)
            partes = data.get("partes", [])
        except json.JSONDecodeError:
            return JsonResponse({"error": "Datos inválidos"}, status=400)
            
        if not partes:
            return JsonResponse({"error": "No se enviaron las partes"}, status=400)
            
        try:
            # S3 ensambla el archivo
            resultado = completar_multipart_upload(
                archivo.ruta_almacenamiento,
                archivo.upload_id,
                partes
            )
            
            # Actualizamos el modelo
            archivo.tamano = resultado["tamano"]
            archivo.hash_sha256 = resultado["etag"]  # El ETag sirve como hash de integridad de S3
            archivo.estado = EstadoArchivo.COMPLETO
            archivo.save()
            
            return JsonResponse({"status": "ok", "archivo_id": archivo.pk})
            
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


class CancelarArchivoView(AdminRequeridoMixin, View):
    """Aborta una carga incompleta."""
    
    def post(self, request, archivo_id):
        archivo = get_object_or_404(Archivo, pk=archivo_id, estado=EstadoArchivo.CARGANDO)
        
        abortar_multipart_upload(archivo.ruta_almacenamiento, archivo.upload_id)
        
        archivo.estado = EstadoArchivo.INCORRECTO
        archivo.save()
        
        return JsonResponse({"status": "cancelado", "archivo_id": archivo.pk})
