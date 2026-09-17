"""Limpia estudios de desarrollo y vacía el bucket configurado de MinIO.

Uso desde la raíz del proyecto:

    .\\.venv\\Scripts\\python.exe limpiar_datos_prueba.py
    .\\.venv\\Scripts\\python.exe limpiar_datos_prueba.py --confirmar

Sin ``--confirmar`` solo muestra un resumen. Queda bloqueado con DEBUG=False.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.conf import settings
from django.db import connection, transaction

from apps.accesos.models import Autorizacion
from apps.archivos.models import Archivo
from apps.archivos.services.storage import get_s3_client
from apps.estudios.models import Estudio, ImportacionEstudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo, Usuario


def contar_objetos_minio():
    """Cuenta objetos del bucket configurado sin descargar contenido."""

    cliente = get_s3_client()
    paginator = cliente.get_paginator("list_objects_v2")
    return sum(
        len(pagina.get("Contents", []))
        for pagina in paginator.paginate(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
    )


def obtener_resumen():
    """Obtiene conteos sin modificar MySQL ni MinIO."""

    return {
        "usuarios": Usuario.objects.count(),
        "odontologos": Odontologo.objects.count(),
        "pacientes": Paciente.objects.count(),
        "estudios": Estudio.objects.count(),
        "archivos": Archivo.objects.count(),
        "importaciones": ImportacionEstudio.objects.count(),
        "autorizaciones": Autorizacion.objects.count(),
        "objetos_minio": contar_objetos_minio(),
        "papelera_minio": contar_papelera_minio(),
    }


def ruta_papelera_minio():
    """Devuelve la papelera local solo cuando se usa el MinIO del proyecto."""

    endpoint = settings.AWS_S3_ENDPOINT_URL or ""
    if not endpoint.startswith(("http://127.0.0.1", "http://localhost")):
        return None
    base = Path(settings.BASE_DIR) / ".local"
    configurada = os.getenv("MINIO_DATA_DIR")
    if configurada:
        raiz = Path(configurada)
        if not raiz.is_absolute():
            raiz = Path(settings.BASE_DIR) / raiz
    else:
        candidatos = [base / "minio-data"]
        raiz = next(
            (candidato for candidato in candidatos if (candidato / ".minio.sys").exists()),
            candidatos[-1],
        )
    return raiz / ".minio.sys" / "tmp" / ".trash"


def contar_papelera_minio():
    """Cuenta archivos pendientes de limpieza física en MinIO local."""

    papelera = ruta_papelera_minio()
    if not papelera or not papelera.exists():
        return 0
    return sum(1 for elemento in papelera.rglob("*") if elemento.is_file())


def vaciar_papelera_minio():
    """Elimina la papelera física local, si MinIO la dejó accesible."""

    papelera = ruta_papelera_minio()
    if not papelera or not papelera.exists():
        return 0
    cantidad = contar_papelera_minio()
    shutil.rmtree(papelera)
    return cantidad


def vaciar_minio():
    """Elimina objetos y cargas multipart incompletas del bucket configurado."""

    cliente = get_s3_client()
    paginator = cliente.get_paginator("list_objects_v2")
    eliminados = 0

    for pagina in paginator.paginate(Bucket=settings.AWS_STORAGE_BUCKET_NAME):
        claves = [objeto["Key"] for objeto in pagina.get("Contents", [])]
        for inicio in range(0, len(claves), 1000):
            lote = claves[inicio:inicio + 1000]
            if not lote:
                continue
            respuesta = cliente.delete_objects(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Delete={
                    "Objects": [{"Key": clave} for clave in lote],
                    "Quiet": True,
                },
            )
            errores = respuesta.get("Errors", [])
            if errores:
                detalle = "; ".join(
                    f"{error.get('Key', '?')}: {error.get('Message', 'error')}"
                    for error in errores[:3]
                )
                raise RuntimeError(
                    f"MinIO rechazó {len(errores)} eliminaciones ({detalle})."
                )
            eliminados += len(lote)

    multipart = cliente.get_paginator("list_multipart_uploads")
    for pagina in multipart.paginate(Bucket=settings.AWS_STORAGE_BUCKET_NAME):
        for carga in pagina.get("Uploads", []):
            cliente.abort_multipart_upload(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=carga["Key"],
                UploadId=carga["UploadId"],
            )

    return eliminados


def limpiar_base():
    """Borra datos operativos de estudios y conserva las cuentas."""

    with transaction.atomic():
        # La auditoría se conserva y se desvincula antes del borrado. La FK de
        # la instalación local de MySQL está en RESTRICT aunque el modelo use
        # SET_NULL.
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE log_actividad "
                "SET id_estudio = NULL "
                "WHERE id_estudio IS NOT NULL"
            )

        archivos = Archivo.objects.all()._raw_delete("default")
        autorizaciones = Autorizacion.objects.all()._raw_delete("default")
        importaciones = ImportacionEstudio.objects.all()._raw_delete("default")
        estudios = Estudio.objects.all()._raw_delete("default")

    return {
        "estudios": estudios,
        "archivos": archivos,
        "importaciones": importaciones,
        "autorizaciones": autorizaciones,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Limpia estudios y vacía el bucket de MinIO de desarrollo."
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Ejecuta la limpieza; sin esta opción solo muestra un resumen.",
    )
    opciones = parser.parse_args()

    if not settings.DEBUG:
        print("ERROR: el script está bloqueado porque DEBUG=False.", file=sys.stderr)
        return 1

    host_minio = urlparse(settings.AWS_S3_ENDPOINT_URL or "").hostname
    if host_minio not in {"127.0.0.1", "localhost", "::1"}:
        print(
            "ERROR: el script solo puede vaciar un MinIO local.",
            file=sys.stderr,
        )
        return 1

    try:
        resumen = obtener_resumen()
    except Exception as error:
        print(f"ERROR: no se pudo consultar MySQL o MinIO: {error}", file=sys.stderr)
        return 1

    print(
        "Datos detectados: "
        f"{resumen['estudios']} estudios, "
        f"{resumen['archivos']} archivos, "
        f"{resumen['importaciones']} importaciones, "
        f"{resumen['autorizaciones']} autorizaciones y "
        f"{resumen['objetos_minio']} objetos en MinIO "
        f"({resumen['papelera_minio']} en su papelera local)."
    )
    print(
        "Se conservarán: "
        f"{resumen['usuarios']} usuarios, "
        f"{resumen['odontologos']} odontólogos y "
        f"{resumen['pacientes']} pacientes."
    )

    if not opciones.confirmar:
        print("Vista previa solamente. Repetí con --confirmar para ejecutar.")
        return 0

    try:
        objetos = vaciar_minio()
        papelera = vaciar_papelera_minio()
        borrados = limpiar_base()
    except Exception as error:
        print(
            "ERROR: la limpieza no terminó. Revisá MinIO/MySQL y volvé a ejecutar "
            f"el script. Detalle: {error}",
            file=sys.stderr,
        )
        return 1

    print(
        "Limpieza completa: "
        f"{borrados['estudios']} estudios, "
        f"{borrados['archivos']} archivos, "
        f"{borrados['importaciones']} importaciones y "
        f"{borrados['autorizaciones']} autorizaciones eliminados; "
        f"{objetos} objetos de MinIO eliminados y "
        f"{papelera} elementos de su papelera física eliminados."
    )
    print("Usuarios, odontólogos, pacientes y auditoría conservados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
