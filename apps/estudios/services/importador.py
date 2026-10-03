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
from django.db.models import Case, IntegerField, When

from apps.archivos.services.storage import leer_objeto, sesion_lectura
from apps.archivos.models import Archivo
from apps.core.enums import CategoriaArchivo, FormatoArchivo
from apps.core.carga_log import registrar_carga
from apps.pacientes.models import Paciente
from .identidad import IdentidadesLote


LIMITE_LECTURA_DICOM = 8 * 1024 * 1024
LIMITE_CABECERA_DICOM = 256 * 1024
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
    datos = {
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
    internas = IdentidadesLote()
    for informacion in raiz.findall(".//PatientInfo"):
        internas.agregar({
            "nombre_paciente": " ".join(filter(None, (_texto_xml(informacion, "LastName"), _texto_xml(informacion, "FirstName")))),
            "identificador_paciente": _texto_xml(informacion, "ID"),
            "fecha_nacimiento": _fecha_iso(_texto_xml(informacion, "BirthDate")),
        })
    datos["_validacion_interna"] = internas.resumen()
    return datos


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
            serie_actual = ""
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
            serie_actual = ""
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
                clave = ruta.casefold()
                if clave in rutas_por_serie and rutas_por_serie[clave] != serie_actual:
                    rutas_por_serie[clave] = None
                else:
                    rutas_por_serie[clave] = serie_actual
    return rutas_por_serie




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





def _identidad_dataset(dataset):
    return {
        "nombre_paciente": _nombre_legible(getattr(dataset, "PatientName", "")),
        "identificador_paciente": str(getattr(dataset, "PatientID", "")).strip(),
        "fecha_nacimiento": _fecha_iso(getattr(dataset, "PatientBirthDate", None)),
    }


def _inspeccionar_lote(importacion, control=None):
    """Revisa todas las fuentes clínicas, una por vez, sin leer volúmenes completos."""
    identidades = IdentidadesLote()
    datos_dicom = None
    datos_gwg = None
    extensiones = set()
    referencias = {}
    actualizados = []
    cantidad = 0
    hay_dicom = False
    hay_gwg = False
    prioridad = Case(When(ruta_relativa__iendswith="DICOMDIR", then=0), default=1, output_field=IntegerField())
    archivos = importacion.archivos.only(
        "nombre_archivo", "ruta_relativa", "ruta_almacenamiento", "formato", "categoria", "series_instance_uid",
    ).order_by(prioridad, "pk")

    def guardar_actualizados():
        if actualizados:
            with transaction.atomic():
                if control:
                    control(cantidad, forzar=True)
                Archivo.objects.bulk_update(actualizados, ["formato", "categoria", "series_instance_uid"], batch_size=500)
            actualizados.clear()

    with sesion_lectura():
        for archivo in archivos.iterator(chunk_size=500):
            cantidad += 1
            if control:
                control(cantidad)
            ruta = PurePosixPath(archivo.ruta_relativa or archivo.nombre_archivo)
            extension = ruta.suffix.lower()
            extensiones.add(extension)
            if extension == ".gwg":
                hay_gwg = True
                contenido = leer_objeto(archivo.ruta_almacenamiento, LIMITE_LECTURA_GWG)
                try:
                    detectados = _datos_desde_gwg16(contenido)
                except (UnicodeDecodeError, ET.ParseError, ValueError, zlib.error) as error:
                    identidades.no_legibles += 1
                    registrar_carga("parser_gwg16_error", importacion_id=importacion.pk, archivo_id=archivo.pk, error=error)
                else:
                    interna = detectados.pop("_validacion_interna", {})
                    if interna.get("estado") == "mezclado":
                        identidades.conflictos.update(interna.get("campos_incompatibles", []))
                    identidades.agregar(detectados)
                    if datos_gwg is None:
                        datos_gwg = detectados
                continue
            dicomdir = ruta.name.upper() == "DICOMDIR"
            if not dicomdir and archivo.formato not in {FormatoArchivo.DICOM, FormatoArchivo.OTRO}:
                identidades.no_legibles += 1
                continue
            if not dicomdir and archivo.formato == FormatoArchivo.OTRO:
                if not _es_dicom(leer_objeto(archivo.ruta_almacenamiento, 132)):
                    identidades.no_legibles += 1
                    continue
            hay_dicom = True
            limite = LIMITE_LECTURA_DICOM if dicomdir else LIMITE_CABECERA_DICOM
            if dicomdir and archivo.tamano > limite:
                # Un índice truncado puede ocultar más registros de pacientes.
                identidades.no_legibles += 1
            contenido = leer_objeto(archivo.ruta_almacenamiento, limite)
            cambio = False
            if _es_dicom(contenido) and archivo.formato == FormatoArchivo.OTRO:
                archivo.formato = FormatoArchivo.DICOM
                archivo.categoria = CategoriaArchivo.DICOM
                cambio = True
            try:
                opciones = {} if dicomdir else {"specific_tags": [
                    "PatientName", "PatientID", "PatientBirthDate", "StudyDate", "StudyDescription",
                    "StudyInstanceUID", "SeriesInstanceUID", "Manufacturer", "ManufacturerModelName", "SoftwareVersions",
                ]}
                dataset = pydicom.dcmread(BytesIO(contenido), stop_before_pixels=True, force=False, **opciones)
            except Exception as error:
                identidades.no_legibles += 1
                registrar_carga("parser_dicom_error", importacion_id=importacion.pk, archivo_id=archivo.pk, error=error)
            else:
                detectados = _identidad_dataset(dataset)
                if not dicomdir or detectados["nombre_paciente"] or detectados["identificador_paciente"]:
                    identidades.agregar(detectados)
                for registro in getattr(dataset, "DirectoryRecordSequence", []):
                    if str(getattr(registro, "DirectoryRecordType", "")).upper() == "PATIENT":
                        identidades.agregar(_identidad_dataset(registro))
                detectados.update({
                    "formato": "DICOM", "fecha_estudio": _fecha_iso(getattr(dataset, "StudyDate", None)),
                    "study_instance_uid": str(getattr(dataset, "StudyInstanceUID", "")).strip(),
                    "descripcion": str(getattr(dataset, "StudyDescription", "")).strip()[:255],
                    "software_origen": " ".join(str(getattr(dataset, campo, "")) for campo in
                        ("Manufacturer", "ManufacturerModelName", "SoftwareVersions") if getattr(dataset, campo, None))[:100],
                    "advertencias": ["El identificador DICOM es una sugerencia; confirmá que corresponda al DNI del paciente."],
                })
                rutas = _completar_desde_dicomdir(dataset, detectados)
                for referencia, uid in rutas.items():
                    clave = (ruta.parent / referencia).as_posix().casefold()
                    if clave in referencias and referencias[clave] != uid:
                        referencias[clave] = None  # Una ruta ambigua nunca recibe un UID arbitrario.
                    else:
                        referencias[clave] = uid
                uid = str(getattr(dataset, "SeriesInstanceUID", "")).strip()
                if uid and archivo.series_instance_uid != uid:
                    archivo.series_instance_uid = uid
                    cambio = True
                if datos_dicom is None or (not datos_dicom.get("identificador_paciente") and detectados.get("identificador_paciente")):
                    datos_dicom = detectados
            if cambio:
                actualizados.append(archivo)
                if len(actualizados) >= 500:
                    guardar_actualizados()
        guardar_actualizados()

    # Lookup exacto O(n), no búsqueda por sufijos O(n*m) ni carpetas homónimas.
    if referencias:
        for archivo in importacion.archivos.only("ruta_relativa", "series_instance_uid").iterator(chunk_size=500):
            if control:
                control(cantidad)
            uid = referencias.get(archivo.ruta_relativa.casefold())
            if uid and not archivo.series_instance_uid:
                archivo.series_instance_uid = uid
                actualizados.append(archivo)
                if len(actualizados) >= 500:
                    with transaction.atomic():
                        if control:
                            control(cantidad, forzar=True)
                        Archivo.objects.bulk_update(actualizados, ["series_instance_uid"], batch_size=500)
                    actualizados.clear()
        if actualizados:
            with transaction.atomic():
                if control:
                    control(cantidad, forzar=True)
                Archivo.objects.bulk_update(actualizados, ["series_instance_uid"], batch_size=500)

    if datos_dicom is not None:
        datos = datos_dicom
    elif hay_dicom:
        datos = {"formato": "DICOM", "advertencias": ["Se detectaron archivos DICOM, pero no fue posible leer sus datos clínicos."]}
    elif datos_gwg is not None:
        datos = datos_gwg
    elif hay_gwg:
        datos = {"formato": "GALILEOS", "software_origen": "GALILEOS / GALAXIS",
                 "nombre_paciente": _nombre_desde_carpeta(importacion.nombre_carpeta),
                 "advertencias": ["No se reconoció la versión interna del archivo GALILEOS. Se usó el nombre de la carpeta como sugerencia."]}
    elif extensiones and extensiones <= {".stl", ".ply"}:
        datos = {"formato": "STL" if ".stl" in extensiones else "PLY", "software_origen": "Modelo 3D",
                 "advertencias": ["Los modelos 3D no contienen datos clínicos verificables; seleccioná el paciente manualmente."]}
    elif extensiones and extensiones <= {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        datos = {"formato": "RADIOGRAFIA", "software_origen": "Radiografía digital",
                 "advertencias": ["La radiografía no aporta datos clínicos estructurados; seleccioná el paciente manualmente."]}
    else:
        datos = {"formato": "DESCONOCIDO", "advertencias": ["No fue posible identificar el formato de la carpeta."]}
    validacion = identidades.resumen()
    validacion["archivos_inspeccionados"] = cantidad
    datos["validacion_pacientes"] = validacion
    if validacion["estado"] == "mezclado":
        for campo in ("nombre_paciente", "identificador_paciente", "fecha_nacimiento"):
            datos.pop(campo, None)
        datos.setdefault("advertencias", []).append(
            "La carpeta contiene identidades de pacientes incompatibles. Separá los estudios y cargá una carpeta por paciente. No se permite confirmar este lote."
        )
    elif validacion["estado"] in {"parcial", "no_verificable"}:
        datos.setdefault("advertencias", []).append(
            "No fue posible verificar la identidad en todas las fuentes clínicas. Revisá la carpeta original antes de confirmar; los archivos sin metadatos no garantizan un único paciente."
        )
    return datos


def analizar_importacion(importacion, control=None):
    """Analiza una importación completa y deja el lote listo para confirmación."""

    # Todas las lecturas remotas ocurren antes de abrir la transacción de estado.
    datos = _inspeccionar_lote(importacion, control=control)
    # Solo códigos fijos: nunca el JSON de metadatos ni sus advertencias clínicas.
    formato_log = datos.get("formato")
    if formato_log not in {"DICOM", "GALILEOS", "STL", "PLY", "RADIOGRAFIA"}:
        formato_log = "DESCONOCIDO"
    registrar_carga(f"deteccion_{formato_log.lower()}", importacion_id=importacion.pk,
                    cantidad=len(datos.get("advertencias", [])))
    paciente = None
    identificador = datos.get("identificador_paciente", "")
    if identificador:
        paciente = Paciente.objects.filter(dni=identificador).first()

    with transaction.atomic():
        actual = type(importacion).objects.select_for_update().get(pk=importacion.pk)
        if control:
            control(forzar=True)
        elif actual.estado != "PROCESANDO" or actual.estudio_id:
            from django.core.exceptions import ValidationError
            raise ValidationError("El lote ya no admite resultados de análisis.")
        importacion = actual
        if (actual.datos_detectados or {}).get("_carga"):
            datos["_carga"] = actual.datos_detectados["_carga"]
        if control:
            datos["_analisis"] = {"estado": "completo", "procesados": importacion.cantidad_archivos}
        importacion.datos_detectados = datos
        importacion.paciente_sugerido = paciente
        importacion.save(update_fields=["datos_detectados", "paciente_sugerido", "updated_at"])
        importacion.marcar_pendiente_confirmacion()
    return importacion
