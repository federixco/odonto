"""Índice derivado sin píxeles ni datos identificatorios del paciente.

La geometría, no los nombres de carpeta, determina si una serie admite volumen.
Un índice legible no garantiza que el dispositivo pueda decodificar/renderizar.
"""
import hashlib
import io
import math
import warnings
from collections import defaultdict

import pydicom
from django.conf import settings

# Codecs empaquetados con cornerstone-dicom-image-loader; sin MPEG/JPEG XL.
SYNTAXES = {
    "1.2.840.10008.1.2", "1.2.840.10008.1.2.1", "1.2.840.10008.1.2.2",
    "1.2.840.10008.1.2.5", "1.2.840.10008.1.2.4.50", "1.2.840.10008.1.2.4.51",
    "1.2.840.10008.1.2.4.57", "1.2.840.10008.1.2.4.70", "1.2.840.10008.1.2.4.80",
    "1.2.840.10008.1.2.4.81", "1.2.840.10008.1.2.4.90", "1.2.840.10008.1.2.4.91",
}
VOLUME_SOPS = {"1.2.840.10008.5.1.4.1.1.2", "1.2.840.10008.5.1.4.1.1.4"}
TAGS = [
    "SOPClassUID", "SOPInstanceUID", "StudyInstanceUID", "SeriesInstanceUID",
    "FrameOfReferenceUID", "Rows", "Columns", "NumberOfFrames", "SamplesPerPixel",
    "PhotometricInterpretation", "BitsAllocated", "BitsStored", "HighBit",
    "PixelRepresentation", "ImageOrientationPatient", "ImagePositionPatient",
    "PixelSpacing", "RescaleSlope", "RescaleIntercept", "InstanceNumber",
]


def numeros(dataset, key, length):
    value = dataset.get(key)
    try:
        result = [float(v) for v in value]
        return result if len(result) == length and all(math.isfinite(v) for v in result) else None
    except (TypeError, ValueError):
        return None


def cabecera(contenido, archivo_id, tamano):
    """Lee como máximo el prefijo recibido; nunca descomprime PixelData."""
    if len(contenido) < 132 or contenido[128:132] != b"DICM":
        return None, "No es DICOM Part 10 compatible."
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Un warning del parser puede incluir datos del archivo.
            d = pydicom.dcmread(io.BytesIO(contenido), stop_before_pixels=True, specific_tags=TAGS)
        uid = lambda key: str(d.get(key, ""))[:64]
        rows, cols, frames = int(d.get("Rows", 0)), int(d.get("Columns", 0)), int(d.get("NumberOfFrames", 1))
        bits = int(d.get("BitsAllocated", 0))
        syntax = str(d.file_meta.get("TransferSyntaxUID", ""))
        if rows <= 0 or cols <= 0:
            return None, "Índice DICOMDIR u objeto sin imagen compatible."
        if syntax not in SYNTAXES:
            return None, "Sintaxis de transferencia no soportada por este visor."
        if str(d.get("PhotometricInterpretation", "")) not in {"MONOCHROME1", "MONOCHROME2"} or int(d.get("SamplesPerPixel", 1)) != 1:
            return None, "Este visor DICOM admite imágenes monocromáticas."
        if bits not in {8, 16, 32} or not 1 <= frames <= settings.VISOR_MAX_FRAMES:
            return None, "Dimensiones o cantidad de frames no compatibles."
        estimated = rows * cols * frames * max(4, bits // 8)
        if tamano > settings.VISOR_MAX_IMAGE_BYTES or estimated > settings.VISOR_MAX_IMAGE_BYTES:
            return None, "El objeto excede el límite de memoria para cortes."
        if not uid("SOPInstanceUID") or not uid("StudyInstanceUID") or not uid("SeriesInstanceUID"):
            return None, "Faltan identificadores DICOM de estudio, serie o instancia."
        if not math.isfinite(float(d.get("RescaleSlope", 1))) or not math.isfinite(float(d.get("RescaleIntercept", 0))):
            return None, "Escala de intensidad inválida."
        return {
            "archivo": archivo_id, "bytes": tamano, "sop": uid("SOPClassUID"),
            "instancia": uid("SOPInstanceUID"), "study": uid("StudyInstanceUID"),
            "serie": uid("SeriesInstanceUID"), "referencia": uid("FrameOfReferenceUID"),
            "syntax": syntax, "rows": rows, "columns": cols, "frames": frames,
            "bits": bits, "signed": int(d.get("PixelRepresentation", 0)),
            "orientation": numeros(d, "ImageOrientationPatient", 6),
            "position": numeros(d, "ImagePositionPatient", 3),
            "spacing": numeros(d, "PixelSpacing", 2),
            "slope": float(d.get("RescaleSlope", 1)), "intercept": float(d.get("RescaleIntercept", 0)),
            "number": int(d.get("InstanceNumber", 0)),
        }, None
    except Exception:
        return None, "Cabecera incompleta, corrupta o fuera del prefijo permitido."


def producto(a, b):
    return sum(x * y for x, y in zip(a, b))


def cerca(a, b, tol=1e-4):
    return a is not None and b is not None and len(a) == len(b) and all(abs(x-y) < tol for x, y in zip(a, b))


def agrupar(cabeceras):
    grupos = defaultdict(list)
    for c in cabeceras:
        grupos[(c["study"], c["serie"], c["referencia"])].append(c)
    resultado = []
    for clave, items in grupos.items():
        primero = items[0]
        o = primero["orientation"]
        geometria = bool(o and abs(producto(o[:3], o[:3])-1) < .001 and abs(producto(o[3:], o[3:])-1) < .001 and abs(producto(o[:3], o[3:])) < .001)
        geometria = geometria and all(cerca(i["orientation"], o) and i["position"] for i in items)
        motivo = ""
        if geometria:
            normal = [o[1]*o[5]-o[2]*o[4], o[2]*o[3]-o[0]*o[5], o[0]*o[4]-o[1]*o[3]]
            items.sort(key=lambda i: producto(i["position"], normal))
            distancias = [producto(i["position"], normal) for i in items]
            pasos = [b-a for a, b in zip(distancias, distancias[1:])]
            if pasos and (min(pasos) < .0001 or max(pasos)-min(pasos) > max(.01, min(pasos)*.05)):
                motivo = "Cortes duplicados, espaciado irregular o huecos en la serie."
            # Cornerstone no debe reconstruir una adquisición con desplazamiento lateral (gantry tilt).
            for a, b in zip(items, items[1:]):
                vector = [y-x for x, y in zip(a["position"], b["position"])]
                axial = producto(vector, normal)
                if any(abs(v-axial*n) > .01 for v, n in zip(vector, normal)):
                    motivo = "La serie tiene desplazamiento lateral; solo se ofrecen cortes."
        else:
            items.sort(key=lambda i: (i["number"], i["archivo"]))
            motivo = "Sin geometría espacial consistente; orden por número de instancia (no espacial)."
        if len({i["instancia"] for i in items}) != len(items):
            motivo = "Hay instancias repetidas en la serie."
        if not primero["referencia"] or any(i["sop"] not in VOLUME_SOPS or i["frames"] != 1 for i in items):
            motivo = "Volumen disponible solo para CT/MR clásicos de un frame, con marco de referencia."
        signature = lambda i: (i["rows"], i["columns"], i["bits"], i["signed"], i["slope"], i["intercept"])
        if not primero["spacing"] or min(primero["spacing"]) <= 0 or any(signature(i) != signature(primero) or not cerca(i["spacing"], primero["spacing"]) for i in items):
            motivo = "Dimensiones, escalas o espaciado de píxel inconsistentes."
        frames = sum(i["frames"] for i in items)
        # Float32 reconstruido + buffers de decodificación/GPU: reserva conservadora x4.
        memoria = sum(i["rows"]*i["columns"]*i["frames"]*4 for i in items) * 4 + sum(i["bytes"] for i in items)
        if frames < 3:
            motivo = "Se necesitan al menos tres cortes espaciales para esta vista 3D."
        if memoria > settings.VISOR_MAX_VOLUME_BYTES or frames > settings.VISOR_MAX_FRAMES:
            motivo = "El volumen supera el presupuesto de memoria del visor; usá cortes."
        resultado.append({
            "id": hashlib.sha256("|".join(clave).encode()).hexdigest()[:24],
            "frames": frames, "volumen": not motivo, "motivo": motivo,
            "memoria_estimada": memoria, "archivos": items,
        })
    return resultado
