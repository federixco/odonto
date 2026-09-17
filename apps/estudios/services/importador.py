"""Análisis de carpetas importadas desde equipos odontológicos.

La detección vive en este servicio porque lee y transforma información; no es
una entidad clínica. Solo propone datos al administrador: jamás crea pacientes
ni confirma un estudio automáticamente.
"""

from datetime import datetime
from io import BytesIO
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET
import zlib

import pydicom
from django.db import transaction

from apps.archivos.services.storage import leer_objeto
from apps.core.enums import CategoriaArchivo, FormatoArchivo
from apps.pacientes.models import Paciente


LIMITE_LECTURA_DICOM = 8 * 1024 * 1024
LIMITE_LECTURA_GWG = 2 * 1024 * 1024
LIMITE_XML_GWG = 4 * 1024 * 1024
CABECERA_GWG16 = b"GWG16"


def _clave_gwg16():
    """Reproduce la clave fija usada por GALILEOS Viewer 1.9.

    El generador opera con enteros con signo de 8 bits. Mantener el algoritmo
    explícito permite detectar con claridad si una futura versión deja de ser
    compatible, en lugar de tratar la clave como una contraseña configurable.
    """

    valor = -117
    clave = bytearray()
    for indice in range(12):
        calculado = ((indice + valor) * valor + 31) % 255
        valor = calculado if calculado < 128 else calculado - 256
        clave.append(valor & 0xFF)
    return bytes(clave)


CLAVE_GWG16 = _clave_gwg16()


def _aplicar_xor_gwg16(contenido):
    """Aplica el XOR por palabras de 32 bits que utiliza Wrap&Go.

    Los bytes residuales vuelven al comienzo de la clave; ese detalle difiere
    de un XOR byte a byte continuo y también protege la validación del trailer
    GZIP.
    """

    salida = bytearray(contenido)
    palabras = len(salida) // 4
    palabras_clave = len(CLAVE_GWG16) // 4
    for indice in range(palabras):
        inicio = indice * 4
        inicio_clave = (indice % palabras_clave) * 4
        for desplazamiento in range(4):
            salida[inicio + desplazamiento] ^= CLAVE_GWG16[
                inicio_clave + desplazamiento
            ]
    for indice in range(palabras * 4, len(salida)):
        salida[indice] ^= CLAVE_GWG16[indice - palabras * 4]
    return bytes(salida)


def _descomprimir_gwg16(contenido):
    """Descifra y descomprime un GWG16 con un límite estricto de salida."""

    if not contenido.startswith(CABECERA_GWG16):
        raise ValueError("Cabecera GWG no compatible.")
    if len(contenido) <= len(CABECERA_GWG16):
        raise ValueError("Archivo GWG vacío.")

    comprimido = _aplicar_xor_gwg16(contenido[len(CABECERA_GWG16) :])
    descompresor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    xml = descompresor.decompress(comprimido, LIMITE_XML_GWG + 1)
    if len(xml) > LIMITE_XML_GWG or descompresor.unconsumed_tail:
        raise ValueError("Los metadatos GWG superan el límite permitido.")
    xml += descompresor.flush(LIMITE_XML_GWG + 1 - len(xml))
    if len(xml) > LIMITE_XML_GWG or not descompresor.eof:
        raise ValueError("El contenido GZIP del GWG es inválido.")
    return xml


def _texto_xml(elemento, nombre):
    nodo = elemento.find(f".//{nombre}")
    return (nodo.text or "").strip() if nodo is not None else ""


def _datos_desde_gwg16(contenido):
    """Extrae metadatos clínicos del XML interno de GALILEOS Wrap&Go."""

    xml = _descomprimir_gwg16(contenido)
    texto = xml.decode("utf-8")
    if "<!DOCTYPE" in texto.upper() or "<!ENTITY" in texto.upper():
        raise ValueError("El XML del GWG contiene declaraciones no permitidas.")
    # Algunos exportadores declaran UTF-16 aunque serializan bytes UTF-8.
    texto = re.sub(r"^\s*<\?xml[^>]*\?>", "", texto, count=1)
    raiz = ET.fromstring(texto)
    if raiz.tag != "DataContainerProperties":
        raise ValueError("El XML no corresponde a un contenedor GALILEOS.")

    nombre = _texto_xml(raiz, "FirstName")
    apellido = _texto_xml(raiz, "LastName")
    marca_tiempo = _texto_xml(raiz, "TimeStamp")
    return {
        "formato": "GALILEOS",
        "software_origen": (
            _texto_xml(raiz, "SoftwareVersion") or "GALILEOS / GALAXIS"
        )[:100],
        # El resto del flujo interpreta el primer término como apellido.
        "nombre_paciente": " ".join(
            parte for parte in (apellido, nombre) if parte
        ),
        "identificador_paciente": _texto_xml(raiz, "ID")[:100],
        "fecha_nacimiento": _fecha_iso(_texto_xml(raiz, "BirthDate")),
        "fecha_estudio": _fecha_iso(marca_tiempo[:8]),
        "descripcion": "Estudio GALILEOS",
        "scan_id": _texto_xml(raiz, "ScanID")[:100],
        "version_formato": _texto_xml(raiz, "Version")[:30],
        "data_source": _texto_xml(raiz, "DataSource")[:50],
        "parser": "galileos-gwg16-v1",
        "advertencias": [
            "Los datos se extrajeron del archivo GALILEOS. Confirmá que correspondan al paciente antes de continuar."
        ],
    }


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


def _nombre_desde_carpeta(nombre):
    """Normaliza el nombre sugerido por una carpeta GALILEOS o WeTransfer."""

    if nombre.lower().startswith("wetransfer_"):
        nombre = nombre[11:]
        nombre = re.sub(r"_\d{4}-\d{2}-\d{2}.*$", "", nombre)
        nombre = nombre.replace("-", " ")

    palabras = []
    for palabra in nombre.split():
        if (
            len(palabra) > 1
            and palabra[0].islower()
            and palabra[1:].isupper()
        ):
            palabras.append(palabra.capitalize())
        else:
            palabras.append(palabra.title())
    nombre = " ".join(palabras).strip()
    return nombre[:-4] if nombre.lower().endswith(" gal") else nombre


def _galileos_detectado(importacion):
    """Lee GWG16 y conserva el nombre de carpeta como fallback seguro."""

    archivo = importacion.archivos.filter(ruta_relativa__iendswith=".gwg").first()
    if not archivo:
        return None

    nombre_carpeta = _nombre_desde_carpeta(importacion.nombre_carpeta)
    contenido = leer_objeto(archivo.ruta_almacenamiento, LIMITE_LECTURA_GWG)
    try:
        datos = _datos_desde_gwg16(contenido)
    except (UnicodeDecodeError, ET.ParseError, ValueError, zlib.error):
        return {
            "formato": "GALILEOS",
            "software_origen": "GALILEOS / GALAXIS",
            "nombre_paciente": nombre_carpeta,
            "advertencias": [
                "No se reconoció la versión interna del archivo GALILEOS. Se usó el nombre de la carpeta como sugerencia."
            ],
        }

    if not datos["nombre_paciente"]:
        datos["nombre_paciente"] = nombre_carpeta
        datos["advertencias"].append(
            "El archivo GALILEOS no contenía un nombre; se usó el nombre de la carpeta."
        )
    return datos


def _formato_no_dicom(importacion):
    """Clasifica formatos no DICOM y profundiza en GALILEOS GWG16."""

    rutas = [archivo.ruta_relativa.lower() for archivo in importacion.archivos.all()]
    extensiones = {PurePosixPath(ruta).suffix for ruta in rutas}
    galileos = _galileos_detectado(importacion)
    if galileos:
        return galileos
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
