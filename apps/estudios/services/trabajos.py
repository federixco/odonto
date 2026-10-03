"""Cola durable en el JSON existente. Un worker independiente procesa cada lote.

Los tokens cercan resultados tardíos; la reserva expira si el proceso se cae.
No contiene nombres ni identificadores clínicos en el progreso del trabajo.
"""
import logging
from datetime import timedelta
from time import monotonic
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.enums import EstadoArchivo, EstadoImportacion
from apps.archivos.services.storage import calcular_sha256_objeto, sesion_lectura
from apps.estudios.models import ImportacionEstudio

logger = logging.getLogger(__name__)
CLAVE = "_analisis"
RESERVA_SEGUNDOS = 180
MAX_INTENTOS = 3


class AnalisisInterrumpido(Exception):
    pass


def encolar(lote):
    with transaction.atomic():
        actual = ImportacionEstudio.objects.select_for_update().get(pk=lote.pk)
        if actual.estudio_id or actual.estado == EstadoImportacion.CONFIRMADA:
            raise ValidationError("La importación ya está confirmada.")
        if actual.estado in {EstadoImportacion.PROCESANDO, EstadoImportacion.PENDIENTE_CONFIRMACION}:
            return actual
        actual.marcar_procesando()
        datos = dict(actual.datos_detectados or {})
        datos[CLAVE] = {"estado": "pendiente", "intentos": 0, "procesados": 0}
        actual.datos_detectados = datos
        actual.save(update_fields=["datos_detectados", "updated_at"])
        return actual


def reservar():
    # Una selección acotada; las reservas vencidas vuelven a estar disponibles.
    ahora = timezone.now()
    with transaction.atomic():
        from django.db.models import Q
        candidatos = ImportacionEstudio.objects.select_for_update(skip_locked=True).filter(
            estado=EstadoImportacion.PROCESANDO,
        ).filter(Q(datos_detectados___analisis__estado="pendiente") | Q(datos_detectados___analisis__vence__lte=ahora.isoformat()) | Q(datos_detectados___analisis__isnull=True)).filter(
            Q(datos_detectados___analisis__disponible__isnull=True) | Q(datos_detectados___analisis__disponible__lte=ahora.isoformat())
        ).order_by("updated_at", "pk")[:20]
        for lote in candidatos:
            datos = dict(lote.datos_detectados or {})
            job = dict(datos.get(CLAVE) or {})
            if job.get("estado") == "en_curso" and job.get("vence", "") > ahora.isoformat():
                continue
            intentos = job.get("intentos", 0)
            if intentos >= MAX_INTENTOS:
                lote.estado = EstadoImportacion.ERROR
                job.update(estado="error", mensaje="El análisis agotó los reintentos. Podés volver a solicitarlo.")
            else:
                job.update(estado="en_curso", token=uuid4().hex, intentos=intentos + 1,
                           vence=(ahora + timedelta(seconds=RESERVA_SEGUNDOS)).isoformat(), procesados=0)
            datos[CLAVE] = job
            lote.datos_detectados = datos
            lote.save(update_fields=["estado", "datos_detectados", "updated_at"])
            if lote.estado == EstadoImportacion.PROCESANDO:
                return lote, job["token"]
    return None


class ControlAnalisis:
    def __init__(self, lote_id, token):
        self.lote_id, self.token = lote_id, token
        self.ultima = 0
        self.procesados = 0
        self.fase = "verificacion"

    def __call__(self, procesados=None, forzar=False):
        if procesados is not None:
            self.procesados = procesados
        if not forzar and monotonic() - self.ultima < 2:
            return
        with transaction.atomic():
            lote = ImportacionEstudio.objects.select_for_update().get(pk=self.lote_id)
            datos = dict(lote.datos_detectados or {})
            job = dict(datos.get(CLAVE) or {})
            if lote.estado != EstadoImportacion.PROCESANDO or job.get("token") != self.token:
                raise AnalisisInterrumpido()
            job.update(procesados=self.procesados, fase=self.fase, vence=(timezone.now() + timedelta(seconds=RESERVA_SEGUNDOS)).isoformat())
            datos[CLAVE] = job
            lote.datos_detectados = datos
            lote.save(update_fields=["datos_detectados", "updated_at"])
        self.ultima = monotonic()


def procesar_uno():
    reserva = reservar()
    if not reserva:
        return False
    lote, token = reserva
    control = ControlAnalisis(lote.pk, token)
    try:
        # El hash completo ya no bloquea la respuesta HTTP de cada archivo.
        # Se lee en bloques y se renueva la reserva también entre bloques.
        with sesion_lectura():
            verificados = lote.archivos.filter(estado=EstadoArchivo.COMPLETO).exclude(hash_sha256__isnull=True).count()
            for archivo in lote.archivos.filter(estado=EstadoArchivo.COMPLETO, hash_sha256__isnull=True).iterator(chunk_size=100):
                control(verificados, forzar=True)
                resumen = calcular_sha256_objeto(archivo.ruta_almacenamiento, control=control)
                with transaction.atomic():
                    control(forzar=True)
                    lote.archivos.filter(pk=archivo.pk, estado=EstadoArchivo.COMPLETO).update(hash_sha256=resumen)
                verificados += 1
        control.fase = "metadatos"
        control(0, forzar=True)
        from .importador import analizar_importacion
        analizar_importacion(lote, control=control)
    except AnalisisInterrumpido:
        pass  # Cancelado o recuperado por otro worker: no escribir un error tardío.
    except Exception:
        logger.exception("Fallo del análisis del lote %s", lote.pk)
        with transaction.atomic():
            actual = ImportacionEstudio.objects.select_for_update().get(pk=lote.pk)
            datos = dict(actual.datos_detectados or {})
            job = dict(datos.get(CLAVE) or {})
            if actual.estado == EstadoImportacion.PROCESANDO and job.get("token") == token:
                job.update(estado="pendiente" if job["intentos"] < MAX_INTENTOS else "error")
                job["disponible"] = (timezone.now() + timedelta(seconds=5 * (2 ** job["intentos"]))).isoformat()
                if job["estado"] == "error":
                    actual.estado = EstadoImportacion.ERROR
                datos[CLAVE] = job
                actual.datos_detectados = datos
                actual.save(update_fields=["estado", "datos_detectados", "updated_at"])
    return True
