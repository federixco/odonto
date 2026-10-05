"""Caché reconstruible del visor: sin migraciones y sin objetos clínicos en disco.

Los .pedido son avisos idempotentes al worker existente, no estados de negocio.
La huella invalida resultados al cambiar archivos. MySQL evita trabajo duplicado.
"""
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from django.conf import settings
from apps.archivos.models import Archivo
from apps.archivos.services.storage import leer_objeto, sesion_lectura
from apps.core.concurrencia import bloquear_recurso, RecursoOcupado
from apps.core.enums import EstadoArchivo, EstadoEstudio
from apps.estudios.models import Estudio
from .visor_dicom import agrupar, cabecera


def archivos_disponibles(estudio):
    return estudio.archivos.filter(estado=EstadoArchivo.COMPLETO).order_by("pk")


def huella(estudio):
    filas = list(archivos_disponibles(estudio).values_list("pk", "hash_sha256", "tamano", "formato", "ruta_almacenamiento", "updated_at"))
    politica = (2, settings.VISOR_MAX_VOLUME_BYTES, settings.VISOR_MAX_IMAGE_BYTES,
                settings.VISOR_MAX_FRAMES, settings.VISOR_HEADER_BYTES, settings.VISOR_MAX_FILES)
    return hashlib.sha256(repr((politica, filas)).encode()).hexdigest()


def directorio():
    ruta = Path(settings.VISOR_CACHE_DIR)
    ruta.mkdir(parents=True, exist_ok=True, mode=0o700)
    return ruta


def guardar(ruta, datos):
    """Publicación atómica: ningún lector recibe un JSON a medio escribir."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=ruta.parent, delete=False) as f:
        json.dump(datos, f, allow_nan=False)
        temporal = f.name
    try:
        os.replace(temporal, ruta)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def leer_cache(estudio, fingerprint):
    ruta = directorio() / f"{estudio.pk}.json"
    try:
        if time.time() - ruta.stat().st_mtime > settings.VISOR_CACHE_TTL:
            return None
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if datos.get("huella") == fingerprint else None
    except (OSError, ValueError):
        return None


def solicitar(estudio, *, reintentar=False):
    fingerprint = huella(estudio)
    datos = leer_cache(estudio, fingerprint)
    pedido = directorio() / f"{estudio.pk}.pedido"
    if datos and not (reintentar and datos.get("estado") == "error"):
        # Mientras el worker reintenta, el polling no debe recuperar el error viejo.
        if datos.get("estado") != "error" or not pedido.exists():
            return datos
    # No cambiar el mtime en cada polling: conserva el orden de atención.
    if not pedido.exists():
        guardar(pedido, {"huella": fingerprint})
    return {"estado": "preparando", "series": [], "omitidos": []}


def preparar(estudio):
    """Una cabecera acotada por objeto; no se leen ni decodifican píxeles."""
    fingerprint = huella(estudio)
    cabeceras, omitidos = [], []
    archivos = archivos_disponibles(estudio).exclude(formato__in=["STL", "PLY", "JPG", "PNG", "TIFF", "PDF"])
    if archivos.count() > settings.VISOR_MAX_FILES:
        raise ValueError("Límite de archivos")
    with sesion_lectura():
        for archivo in archivos.iterator(chunk_size=100):
            datos = leer_objeto(archivo.ruta_almacenamiento, min(archivo.tamano, settings.VISOR_HEADER_BYTES))
            metadata, motivo = cabecera(datos, archivo.pk, archivo.tamano)
            if metadata:
                cabeceras.append(metadata)
            else:
                omitidos.append({"archivo": archivo.pk, "motivo": motivo})
    return {"huella": fingerprint, "estado": "listo", "series": agrupar(cabeceras), "omitidos": omitidos}


def procesar_visor_uno():
    """Atiende un índice después de cada turno de importaciones, incluso anteriores."""
    raiz = directorio()
    def modificado(ruta):
        try:
            return ruta.stat().st_mtime
        except FileNotFoundError:
            return 0
    for pedido in sorted(raiz.glob("*.pedido"), key=modificado):
        if not pedido.stem.isdecimal():
            continue
        try:
            with bloquear_recurso(f"indice-visor:{pedido.stem}"):
                if not pedido.exists():
                    continue
                estudio = Estudio.objects.exclude(estado=EstadoEstudio.ELIMINADO).filter(pk=int(pedido.stem)).first()
                if not estudio:
                    pedido.unlink(missing_ok=True)
                    (raiz / f"{pedido.stem}.json").unlink(missing_ok=True)
                    continue
                fingerprint = huella(estudio)
                try:
                    datos = preparar(estudio)
                except Exception:
                    # No incluir excepciones del SDK: pueden revelar claves/URLs/PHI.
                    datos = {"huella": fingerprint, "estado": "error", "series": [], "omitidos": []}
                if fingerprint == huella(estudio):
                    guardar(raiz / f"{estudio.pk}.json", datos)
                    pedido.unlink(missing_ok=True)
                return True
        except RecursoOcupado:
            continue
    # Solo metadatos expirados; nunca tocar estudios ni objetos S3.
    for cache in raiz.glob("*.json"):
        if time.time() - modificado(cache) > settings.VISOR_CACHE_TTL:
            cache.unlink(missing_ok=True)
    return False
