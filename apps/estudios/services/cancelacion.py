import logging
from django.db import transaction
from apps.core.concurrencia import bloquear_recurso, RecursoOcupado
from apps.core.enums import EstadoArchivo, EstadoImportacion
from apps.archivos.services.storage import abortar_multipart_upload, eliminar_objeto
from apps.estudios.models import ImportacionEstudio

logger = logging.getLogger(__name__)


def limpiar_cancelada(lote, limite=5):
    if lote.estado != EstadoImportacion.CANCELADA or lote.estudio_id:
        return 0
    for archivo in lote.archivos.exclude(estado=EstadoArchivo.PURGADO).order_by("pk")[:limite]:
        try:
            with bloquear_recurso(f"archivo:{archivo.pk}") as comprobar:
                archivo.refresh_from_db()
                if archivo.estudio_id:
                    continue
                if archivo.upload_id and not abortar_multipart_upload(archivo.ruta_almacenamiento, archivo.upload_id):
                    continue
                eliminar_objeto(archivo.ruta_almacenamiento)
                with transaction.atomic():
                    comprobar()
                    archivo.estado, archivo.upload_id = EstadoArchivo.PURGADO, None
                    archivo.save(update_fields=["estado", "upload_id", "updated_at"])
        except RecursoOcupado:
            continue
        except Exception:
            logger.exception("Limpieza pendiente del archivo %s", archivo.pk)
    return lote.archivos.exclude(estado=EstadoArchivo.PURGADO).count()


def limpiar_cancelaciones():
    # EXISTS encuentra lotes con al menos un archivo pendiente de limpieza.
    from django.db.models import Exists, OuterRef
    from apps.archivos.models import Archivo
    pendientes = Archivo.objects.filter(importacion_id=OuterRef("pk")).exclude(estado=EstadoArchivo.PURGADO)
    from django.db.models import Q
    from django.utils import timezone
    lotes = ImportacionEstudio.objects.filter(estado=EstadoImportacion.CANCELADA, estudio__isnull=True).filter(Exists(pendientes)).filter(
        Q(datos_detectados___limpieza__disponible__isnull=True) | Q(datos_detectados___limpieza__disponible__lte=timezone.now().isoformat())
    ).order_by("updated_at", "pk")[:1]
    for lote in lotes:
        restantes = limpiar_cancelada(lote, limite=1)
        # Rotar lotes inaccesibles para no bloquear la limpieza de otros.
        from datetime import timedelta
        with transaction.atomic():
            actual = ImportacionEstudio.objects.select_for_update().get(pk=lote.pk)
            datos = dict(actual.datos_detectados or {})
            datos["_limpieza"] = {"disponible": (timezone.now() + timedelta(seconds=10 if restantes else 0)).isoformat(), "pendientes": restantes}
            actual.datos_detectados = datos
            actual.save(update_fields=["datos_detectados", "updated_at"])
