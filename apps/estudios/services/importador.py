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
    """Prioriza DICOMDIR sin importar su posición dentro de la carpeta."""

    dicomdir = importacion.archivos.filter(
        ruta_relativa__iendswith="DICOMDIR"
    ).first()
    archivos = []
    if dicomdir:
        archivos.append(dicomdir)
    archivos.extend(
        importacion.archivos.exclude(pk=getattr(dicomdir, "pk", None)).order_by("id")[:25]
    )
    for archivo in archivos:
        contenido = leer_objeto(archivo.ruta_almacenamiento, LIMITE_LECTURA_DICOM)
        if _es_dicom(contenido):
            return archivo, contenido
    return None, None


def _nombre_legible(valor):
    """Convierte APELLIDO^NOMBRES de DICOM a texto legible y sin huecos."""

    return " ".join(str(valor or "").replace("^", " ").split())


def _completar_desde_dicomdir(dataset, datos):
    """Lee paciente, estudio y series almacenados como registros de DICOMDIR."""

    serie_actual = ""
    rutas_por_serie = {}
    for registro in getattr(dataset, "DirectoryRecordSequence", []):
        tipo = str(getattr(registro, "DirectoryRecordType", "")).upper()
        if tipo == "PATIENT":
            datos["nombre_paciente"] = _nombre_legible(
                getattr(registro, "PatientName", datos["nombre_paciente"])
            )
            datos["identificador_paciente"] = str(
                getattr(registro, "PatientID", datos["identificador_paciente"])
            ).strip()
            datos["fecha_nacimiento"] = (
                _fecha_iso(getattr(registro, "PatientBirthDate", None))
                or datos["fecha_nacimiento"]
            )
        elif tipo == "STUDY":
            datos["fecha_estudio"] = (
                _fecha_iso(getattr(registro, "StudyDate", None))
                or datos["fecha_estudio"]
            )
            datos["study_instance_uid"] = str(
                getattr(registro, "StudyInstanceUID", datos["study_instance_uid"])
            ).strip()
            datos["descripcion"] = str(
                getattr(registro, "StudyDescription", datos["descripcion"])
            ).strip()[:255]
        elif tipo == "SERIES":
            serie_actual = str(getattr(registro, "SeriesInstanceUID", "")).strip()
        elif tipo in {"IMAGE", "RAW DATA"} and serie_actual:
            referencia = getattr(registro, "ReferencedFileID", None)
            if referencia:
                if not isinstance(referencia, (str, bytes)) and hasattr(referencia, "__iter__"):
                    ruta = "/".join(str(parte) for parte in referencia)
                else:
                    ruta = str(referencia).replace("\\", "/")
                rutas_por_serie[ruta.lower()] = serie_actual
    return rutas_por_serie


def _guardar_series_en_archivos(importacion, rutas_por_serie):
    """Anota el UID de serie en cada archivo sin crear una tabla adicional."""

    if not rutas_por_serie:
        return
    actualizados = []
    for archivo in importacion.archivos.all():
        ruta = archivo.ruta_relativa.lower()
        uid = next(
            (uid for sufijo, uid in rutas_por_serie.items() if ruta.endswith(sufijo)),
            None,
        )
        if uid and archivo.series_instance_uid != uid:
            archivo.series_instance_uid = uid
            actualizados.append(archivo)
    if actualizados:
        type(actualizados[0]).objects.bulk_update(
            actualizados, ["series_instance_uid"], batch_size=500
        )


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

    nombre = _nombre_legible(getattr(dataset, "PatientName", ""))
    identificador = str(getattr(dataset, "PatientID", "")).strip()
    software = " ".join(
        str(getattr(dataset, campo, "")).strip()
        for campo in ("Manufacturer", "ManufacturerModelName", "SoftwareVersions")
        if getattr(dataset, campo, None)
    )[:100]
    datos = {
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
    rutas_por_serie = _completar_desde_dicomdir(dataset, datos)
    _guardar_series_en_archivos(importacion, rutas_por_serie)
    if not datos["nombre_paciente"]:
        advertencias.append("No se encontró el nombre del paciente en los metadatos DICOM.")
    return datos


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
