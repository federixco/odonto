"""Detección segura de metadatos en carpetas importadas.

Los detectores solo proponen información. Nunca crean un estudio ni aceptan un
paciente automáticamente: el administrador siempre confirma el resultado.
"""

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import PurePosixPath

from django.db import transaction

from apps.core.enums import CategoriaArchivo, FormatoArchivo, FormatoImportacion, NivelConfianza
from apps.pacientes.models import Paciente
from apps.archivos.services.storage import leer_objeto

from ..models import SerieDicom


@dataclass
class SerieDetectada:
    uid: str
    modalidad: str = ""
    descripcion: str = ""
    numero: int | None = None
    cantidad: int = 0


@dataclass
class ResultadoDeteccion:
    formato: str = FormatoImportacion.DESCONOCIDO
    software: str = ""
    confianza: str = NivelConfianza.BAJA
    nombre_paciente: str = ""
    identificador_paciente: str = ""
    fecha_nacimiento: object | None = None
    fecha_estudio: object | None = None
    descripcion: str = ""
    study_uid: str = ""
    advertencias: list[str] = field(default_factory=list)
    series: list[SerieDetectada] = field(default_factory=list)


def _fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(str(valor), "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def _dicom_dir(importacion):
    return importacion.archivos.filter(ruta_relativa__iendswith="DICOMDIR").first()


def _valor_dicom_explicito(datos, grupo, elemento):
    """Obtiene un valor corto de DICOM Explicit VR Little Endian sin librerías.

    Es suficiente para las etiquetas administrativas que exportan los equipos
    del centro. Si el formato usa otra codificación, el resultado queda vacío y
    la pantalla pide confirmación manual, en lugar de inventar un dato.
    """
    marca = bytes((grupo & 255, grupo >> 8, elemento & 255, elemento >> 8))
    posicion = datos.find(marca)
    if posicion < 0 or posicion + 8 > len(datos):
        return ""
    vr = datos[posicion + 4:posicion + 6]
    if vr in {b"OB", b"OD", b"OF", b"OL", b"OW", b"SQ", b"UC", b"UN", b"UR", b"UT"}:
        if posicion + 12 > len(datos): return ""
        longitud = int.from_bytes(datos[posicion + 8:posicion + 12], "little")
        inicio = posicion + 12
    else:
        longitud = int.from_bytes(datos[posicion + 6:posicion + 8], "little")
        inicio = posicion + 8
    if longitud > 4096 or inicio + longitud > len(datos): return ""
    return datos[inicio:inicio + longitud].decode("latin-1", errors="ignore").strip(" \x00")


def _detectar_dicom_sin_libreria(contenido):
    if len(contenido) < 132 or contenido[128:132] != b"DICM":
        return None
    resultado = ResultadoDeteccion(
        formato=FormatoImportacion.DICOM,
        software=" ".join(filter(None, [
            _valor_dicom_explicito(contenido, 0x0008, 0x0070),
            _valor_dicom_explicito(contenido, 0x0008, 0x1090),
        ]))[:100],
        confianza=NivelConfianza.ALTA,
        nombre_paciente=_valor_dicom_explicito(contenido, 0x0010, 0x0010).replace("^", " "),
        identificador_paciente=_valor_dicom_explicito(contenido, 0x0010, 0x0020),
        fecha_nacimiento=_fecha(_valor_dicom_explicito(contenido, 0x0010, 0x0030)),
        fecha_estudio=_fecha(_valor_dicom_explicito(contenido, 0x0008, 0x0020)),
        descripcion=_valor_dicom_explicito(contenido, 0x0008, 0x1030)[:255],
        study_uid=_valor_dicom_explicito(contenido, 0x0020, 0x000D),
        advertencias=["El identificador DICOM es una sugerencia; confirmá que corresponda al DNI del paciente."],
    )
    if not resultado.nombre_paciente:
        resultado.confianza = NivelConfianza.MEDIA
        resultado.advertencias.append("No se encontró el nombre del paciente en los metadatos DICOM.")
    return resultado


def _es_galileos(archivos):
    rutas = [archivo.ruta_relativa.lower() for archivo in archivos]
    return any(ruta.endswith(".gwg") for ruta in rutas) and any("_vol_" in ruta for ruta in rutas)


def _detectar_dicom(importacion):
    """Lee DICOMDIR o una cabecera DICOM; no interpreta ni ejecuta binarios."""
    archivo = _dicom_dir(importacion) or importacion.archivos.order_by("id").first()
    if not archivo:
        return None
    contenido = leer_objeto(archivo.ruta_almacenamiento, max_bytes=8 * 1024 * 1024)
    # pydicom ofrece un recorrido rico de DICOMDIR si está disponible. La
    # implementación ligera de abajo mantiene el flujo operativo sin depender
    # de un paquete externo para las etiquetas básicas del centro.
    try:
        import pydicom
    except ImportError:
        return _detectar_dicom_sin_libreria(contenido)
    try:
        dataset = pydicom.dcmread(BytesIO(contenido), stop_before_pixels=True, force=False)
    except Exception:
        return _detectar_dicom_sin_libreria(contenido)

    resultado = ResultadoDeteccion(
        formato=FormatoImportacion.DICOM,
        software=" ".join(
            str(getattr(dataset, campo, "")).strip()
            for campo in ("Manufacturer", "ManufacturerModelName", "SoftwareVersions")
            if getattr(dataset, campo, None)
        )[:100],
        confianza=NivelConfianza.ALTA,
    )
    resultado.nombre_paciente = str(getattr(dataset, "PatientName", "")).replace("^", " ").strip()
    resultado.identificador_paciente = str(getattr(dataset, "PatientID", "")).strip()
    resultado.fecha_nacimiento = _fecha(getattr(dataset, "PatientBirthDate", None))
    resultado.fecha_estudio = _fecha(getattr(dataset, "StudyDate", None))
    resultado.descripcion = str(getattr(dataset, "StudyDescription", "")).strip()[:255]
    resultado.study_uid = str(getattr(dataset, "StudyInstanceUID", "")).strip()

    # Un DICOMDIR conserva las series y permite mostrar una propuesta más útil.
    actual = None
    for registro in getattr(dataset, "DirectoryRecordSequence", []):
        tipo = str(getattr(registro, "DirectoryRecordType", "")).upper()
        if tipo == "PATIENT":
            resultado.nombre_paciente = str(getattr(registro, "PatientName", resultado.nombre_paciente)).replace("^", " ").strip()
            resultado.identificador_paciente = str(getattr(registro, "PatientID", resultado.identificador_paciente)).strip()
            resultado.fecha_nacimiento = _fecha(getattr(registro, "PatientBirthDate", None)) or resultado.fecha_nacimiento
        elif tipo == "STUDY":
            resultado.fecha_estudio = _fecha(getattr(registro, "StudyDate", None)) or resultado.fecha_estudio
            resultado.descripcion = str(getattr(registro, "StudyDescription", resultado.descripcion)).strip()[:255]
            resultado.study_uid = str(getattr(registro, "StudyInstanceUID", resultado.study_uid)).strip()
        elif tipo == "SERIES":
            uid = str(getattr(registro, "SeriesInstanceUID", "")).strip()
            if uid:
                actual = SerieDetectada(
                    uid=uid,
                    modalidad=str(getattr(registro, "Modality", "")).strip()[:16],
                    descripcion=str(getattr(registro, "SeriesDescription", "")).strip()[:255],
                    numero=getattr(registro, "SeriesNumber", None),
                )
                resultado.series.append(actual)
        elif tipo in {"IMAGE", "RAW DATA"} and actual:
            actual.cantidad += 1

    if not resultado.nombre_paciente:
        resultado.advertencias.append("No se encontró el nombre del paciente en los metadatos DICOM.")
        resultado.confianza = NivelConfianza.MEDIA
    resultado.advertencias.append("El identificador DICOM es una sugerencia; confirmá que corresponda al DNI del paciente.")
    return resultado


def _detectar_galileos(archivos):
    if not _es_galileos(archivos):
        return None
    return ResultadoDeteccion(
        formato=FormatoImportacion.GALILEOS,
        software="GALILEOS Viewer / GALAXIS",
        confianza=NivelConfianza.ALTA,
        advertencias=[
            "Se detectó un paquete GALILEOS. Se conservará la estructura completa.",
            "El paciente no se infiere de forma confiable en este formato; confirmalo manualmente.",
            "Los ejecutables del paquete se almacenan como datos y nunca se ejecutan desde la plataforma.",
        ],
    )


def _detectar_stl(archivos):
    stls = [a for a in archivos if a.ruta_relativa.lower().endswith(".stl")]
    if not stls or len(stls) != len(archivos):
        return None
    nombres = ", ".join(PurePosixPath(a.ruta_relativa).stem for a in stls[:4])
    return ResultadoDeteccion(
        formato=FormatoImportacion.STL,
        software="Modelo 3D STL",
        confianza=NivelConfianza.MEDIA,
        descripcion=f"Modelos 3D: {nombres}"[:255],
        advertencias=["Los archivos STL no contienen datos clínicos de paciente verificables; seleccioná la ficha manualmente."],
    )


def _detectar_radiografia(archivos):
    extensiones = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    if not archivos or not all(PurePosixPath(a.ruta_relativa).suffix.lower() in extensiones for a in archivos):
        return None
    return ResultadoDeteccion(
        formato=FormatoImportacion.RADIOGRAFIA,
        software="Radiografía digital",
        confianza=NivelConfianza.MEDIA,
        descripcion="Radiografía digital",
        advertencias=["La imagen no aporta datos clínicos estructurados; seleccioná y confirmá al paciente manualmente."],
    )


def detectar_importacion(importacion):
    """Aplica detectores ordenados de mayor evidencia a menor evidencia."""
    archivos = list(importacion.archivos.all())
    resultado = _detectar_dicom(importacion)
    if resultado is None:
        resultado = _detectar_galileos(archivos) or _detectar_stl(archivos) or _detectar_radiografia(archivos)
    if resultado is None:
        resultado = ResultadoDeteccion(advertencias=["No fue posible identificar el formato de la carpeta."])
    return resultado


def guardar_resultado(importacion, resultado):
    """Persiste una sugerencia sin modificar la identidad clínica definitiva."""
    paciente = None
    if resultado.identificador_paciente:
        paciente = Paciente.objects.filter(dni=resultado.identificador_paciente).first()
    with transaction.atomic():
        importacion.formato_detectado = resultado.formato
        importacion.software_origen = resultado.software
        importacion.nivel_confianza = resultado.confianza
        importacion.nombre_paciente_detectado = resultado.nombre_paciente
        importacion.identificador_paciente_detectado = resultado.identificador_paciente
        importacion.fecha_nacimiento_detectada = resultado.fecha_nacimiento
        importacion.fecha_estudio_detectada = resultado.fecha_estudio
        importacion.descripcion_detectada = resultado.descripcion
        importacion.study_instance_uid = resultado.study_uid or None
        importacion.paciente_sugerido = paciente
        importacion.advertencias = resultado.advertencias
        importacion.save()
        for serie in resultado.series:
            SerieDicom.objects.update_or_create(
                importacion=importacion,
                series_instance_uid=serie.uid,
                defaults={"modalidad": serie.modalidad, "descripcion": serie.descripcion, "numero_serie": serie.numero, "cantidad_archivos": serie.cantidad},
            )
        if resultado.formato == FormatoImportacion.DICOM:
            importacion.archivos.update(formato=FormatoArchivo.DICOM, categoria=CategoriaArchivo.DICOM)
        importacion.marcar_pendiente_confirmacion()
    return importacion
