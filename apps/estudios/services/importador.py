"""Análisis de carpetas importadas desde equipos odontológicos.

La detección vive en este servicio porque lee y transforma información; no es
una entidad clínica. Solo propone datos al administrador: jamás crea pacientes
ni confirma un estudio automáticamente.
"""

from datetime import datetime
from io import BytesIO
from pathlib import PurePosixPath

import pydicom
from django.db import transaction

from apps.archivos.services.storage import leer_objeto
from apps.core.enums import CategoriaArchivo, FormatoArchivo
from apps.pacientes.models import Paciente


LIMITE_LECTURA_DICOM = 8 * 1024 * 1024


def _fecha_iso(valor):
    """Convierte fechas DICOM AAAAMMDD al formato ISO usado por el frontend."""

    if not valor:
        return ""
    try:
        return datetime.strptime(str(valor), "%Y%m%d").date().isoformat()
    except (TypeError, ValueError):
        return ""


def _es_dicom(contenido):
    """Reconoce el preámbulo DICOM sin depender de la extensión del archivo."""

    return len(contenido) >= 132 and contenido[128:132] == b"DICM"


def _archivo_dicom_candidato(importacion):
    """Prioriza DICOMDIR y luego inspecciona pocos objetos para ahorrar lecturas."""

    archivos = list(importacion.archivos.order_by("id")[:25])
    archivos.sort(key=lambda archivo: not archivo.ruta_relativa.upper().endswith("DICOMDIR"))
    for archivo in archivos:
        contenido = leer_objeto(archivo.ruta_almacenamiento, LIMITE_LECTURA_DICOM)
        if _es_dicom(contenido):
            return archivo, contenido
    return None, None


def _dicom_detectado(importacion):
    archivo, contenido = _archivo_dicom_candidato(importacion)
    if not archivo:
        return None

    advertencias = [
        "El identificador DICOM es una sugerencia; confirmá que corresponda al DNI del paciente."
    ]
    try:
        dataset = pydicom.dcmread(
            BytesIO(contenido), stop_before_pixels=True, force=False
        )
    except Exception:
        return {
            "formato": "DICOM",
            "software_origen": "",
            "advertencias": [
                "Se detectó una firma DICOM, pero no fue posible leer sus metadatos."
            ],
        }

    nombre = str(getattr(dataset, "PatientName", "")).replace("^", " ").strip()
    identificador = str(getattr(dataset, "PatientID", "")).strip()
    if not nombre:
        advertencias.append("No se encontró el nombre del paciente en los metadatos DICOM.")

    software = " ".join(
        str(getattr(dataset, campo, "")).strip()
        for campo in ("Manufacturer", "ManufacturerModelName", "SoftwareVersions")
        if getattr(dataset, campo, None)
    )[:100]
    return {
        "formato": "DICOM",
        "software_origen": software,
        "nombre_paciente": nombre,
        "identificador_paciente": identificador,
        "fecha_nacimiento": _fecha_iso(getattr(dataset, "PatientBirthDate", None)),
        "fecha_estudio": _fecha_iso(getattr(dataset, "StudyDate", None)),
        "study_instance_uid": str(getattr(dataset, "StudyInstanceUID", "")).strip(),
        "descripcion": str(getattr(dataset, "StudyDescription", "")).strip()[:255],
        "advertencias": advertencias,
    }


def _formato_no_dicom(importacion):
    """Clasificación simple para formatos cuyo análisis profundo no entra al MVP."""

    rutas = [archivo.ruta_relativa.lower() for archivo in importacion.archivos.all()]
    extensiones = {PurePosixPath(ruta).suffix for ruta in rutas}
    if any(ruta.endswith(".gwg") for ruta in rutas):
        return {
            "formato": "GALILEOS",
            "software_origen": "GALILEOS / GALAXIS",
            "advertencias": [
                "Paquete propietario detectado. Seleccioná el paciente manualmente."
            ],
        }
    if extensiones and extensiones <= {".stl", ".ply"}:
        return {
            "formato": "STL" if ".stl" in extensiones else "PLY",
            "software_origen": "Modelo 3D",
            "advertencias": [
                "Los modelos 3D no contienen datos clínicos verificables; seleccioná el paciente manualmente."
            ],
        }
    if extensiones and extensiones <= {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        return {
            "formato": "RADIOGRAFIA",
            "software_origen": "Radiografía digital",
            "advertencias": [
                "La radiografía no aporta datos clínicos estructurados; seleccioná el paciente manualmente."
            ],
        }
    return {
        "formato": "DESCONOCIDO",
        "software_origen": "",
        "advertencias": ["No fue posible identificar el formato de la carpeta."],
    }


def _actualizar_metadatos_archivos(importacion, datos):
    """Ajusta metadatos técnicos sin alterar la relación Archivo -> Estudio."""

    if datos.get("formato") == "DICOM":
        importacion.archivos.update(
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
        )


def analizar_importacion(importacion):
    """Analiza una importación completa y deja el lote listo para confirmación."""

    datos = _dicom_detectado(importacion) or _formato_no_dicom(importacion)
    paciente = None
    identificador = datos.get("identificador_paciente", "")
    if identificador:
        paciente = Paciente.objects.filter(dni=identificador).first()

    with transaction.atomic():
        importacion.datos_detectados = datos
        importacion.paciente_sugerido = paciente
        importacion.save(update_fields=["datos_detectados", "paciente_sugerido", "updated_at"])
        _actualizar_metadatos_archivos(importacion, datos)
        importacion.marcar_pendiente_confirmacion()
    return importacion
