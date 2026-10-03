"""Operaciones de bajo nivel sobre el almacenamiento privado S3/MinIO."""

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


_sesion_lectura = ContextVar("sesion_lectura_s3", default=None)


@contextmanager
def _cliente_lectura():
    """El dueño de la sesión cierra el cliente, incluso si falla get_object."""
    sesion = _sesion_lectura.get()
    if sesion is not None:
        if sesion["cliente"] is None:
            sesion["cliente"] = get_s3_client()
        yield sesion["cliente"]
    else:
        cliente = get_s3_client()
        try:
            yield cliente
        finally:
            cliente.close()


@contextmanager
def sesion_lectura():
    """Reutiliza conexiones durante un análisis, sin cache global de credenciales."""
    if _sesion_lectura.get() is not None:
        yield
        return
    sesion = {"cliente": None}
    token = _sesion_lectura.set(sesion)
    try:
        yield
    finally:
        _sesion_lectura.reset(token)
        if sesion["cliente"] is not None:
            sesion["cliente"].close()


def _codigo_error_s3(error):
    """Extrae el código estable de una respuesta de error S3."""

    return str(error.response.get("Error", {}).get("Code", ""))


def get_s3_client():
    """Construye el cliente sin exponer las credenciales al navegador."""

    try:
        import boto3
        from botocore.config import Config
    except ImportError as error:
        raise ImproperlyConfigured(
            "La integración S3 requiere instalar las dependencias de requirements.txt."
        ) from error

    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=30,
            retries={"mode": "standard", "total_max_attempts": 3},
            s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE},
        ),
    )


def asegurar_bucket():
    """Comprueba el bucket; solo desarrollo puede aprovisionarlo automáticamente."""

    try:
        from botocore.exceptions import ClientError
    except ImportError as error:
        raise ImproperlyConfigured(
            "La integración S3 requiere instalar las dependencias de requirements.txt."
        ) from error

    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
    except ClientError as error:
        if _codigo_error_s3(error) not in {"404", "NoSuchBucket", "NotFound"}:
            s3.close()
            raise
        if not settings.DEBUG:
            s3.close()
            raise ImproperlyConfigured("El bucket privado debe aprovisionarse antes de iniciar producción.") from error
        parametros = {"Bucket": settings.AWS_STORAGE_BUCKET_NAME}
        region = settings.AWS_S3_REGION_NAME
        if region and region != "us-east-1" and not settings.AWS_S3_ENDPOINT_URL:
            parametros["CreateBucketConfiguration"] = {
                "LocationConstraint": region,
            }
        try:
            s3.create_bucket(**parametros)
        except ClientError as create_error:
            if _codigo_error_s3(create_error) not in {
                "BucketAlreadyExists",
                "BucketAlreadyOwnedByYou",
            }:
                s3.close()
                raise
    return s3


def iniciar_multipart_upload(clave_objeto, content_type="application/octet-stream"):
    """Inicia una carga multipartes y devuelve su identificador interno."""

    cliente = asegurar_bucket()
    try:
        respuesta = cliente.create_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=clave_objeto,
            ContentType=content_type,
        )
        return respuesta["UploadId"]
    finally:
        cliente.close()


def generar_urls_prefirmadas(clave_objeto, upload_id, cantidad_partes):
    """Genera permisos temporales de escritura para las partes esperadas."""

    s3 = get_s3_client()
    return [
        {
            "part_number": numero,
            "url": s3.generate_presigned_url(
                ClientMethod="upload_part",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": clave_objeto,
                    "UploadId": upload_id,
                    "PartNumber": numero,
                },
                ExpiresIn=settings.AWS_S3_PRESIGNED_EXPIRATION,
            ),
        }
        for numero in range(1, cantidad_partes + 1)
    ]


def completar_multipart_upload(clave_objeto, upload_id, partes):
    """Ensambla las partes y devuelve tamaño y ETag informativo del objeto."""

    s3 = get_s3_client()
    try:
        s3.complete_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=clave_objeto,
            UploadId=upload_id,
            MultipartUpload={"Parts": partes},
        )
    except Exception as error:
        if str(getattr(error, "response", {}).get("Error", {}).get("Code")) != "NoSuchUpload":
            raise
        # Una respuesta perdida puede dejar el objeto ensamblado. HEAD debe
        # demostrar que existe; un multipart abortado no se trata como éxito.
    head = s3.head_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=clave_objeto,
    )
    return {
        "tamano": head["ContentLength"],
        # En multipartes el ETag no equivale al SHA-256 del archivo completo.
        "etag": head.get("ETag", "").strip('"'),
    }


def calcular_sha256_objeto(clave_objeto, control=None):
    """Calcula el SHA-256 real leyendo el objeto por bloques, sin cargarlo en RAM."""

    digest = hashlib.sha256()
    with _cliente_lectura() as cliente:
        respuesta = cliente.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=clave_objeto)
        cuerpo = respuesta["Body"]
        try:
            while bloque := cuerpo.read(settings.S3_HASH_CHUNK_SIZE):
                if control:
                    control()
                digest.update(bloque)
        finally:
            cuerpo.close()
    return digest.hexdigest()


def leer_objeto(clave_objeto, max_bytes):
    """Lee una porción acotada de un objeto privado para detectar metadatos.

    Los detectores solo necesitan cabeceras o DICOMDIR; este límite evita que
    el proceso de análisis cargue tomografías completas en la memoria del servidor.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes debe ser positivo.")
    with _cliente_lectura() as cliente:
        respuesta = cliente.get_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=clave_objeto,
            Range=f"bytes=0-{max_bytes - 1}",
        )
        cuerpo = respuesta["Body"]
        try:
            return cuerpo.read(max_bytes)
        finally:
            cuerpo.close()


def abortar_multipart_upload(clave_objeto, upload_id):
    """Aborta una carga incompleta y devuelve si S3 confirmó la operación."""

    try:
        get_s3_client().abort_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=clave_objeto,
            UploadId=upload_id,
        )
        return True
    except Exception as error:
        codigo = getattr(error, "response", {}).get("Error", {}).get("Code")
        if str(codigo) in {"404", "NoSuchBucket", "NoSuchUpload", "NotFound"}:
            return True
        return False


def eliminar_objeto(clave_objeto):
    """Elimina un objeto; si el bucket ya no existe, el objetivo ya se cumplió."""

    try:
        get_s3_client().delete_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=clave_objeto,
        )
    except Exception as error:
        codigo = getattr(error, "response", {}).get("Error", {}).get("Code")
        if str(codigo) not in {"404", "NoSuchBucket", "NoSuchKey", "NotFound"}:
            raise
    return True


def generar_url_descarga(clave_objeto, nombre_archivo=None, expiracion=None):
    """Genera una URL prefirmada temporal para descargar el objeto con cabecera attachment."""
    if expiracion is None:
        expiracion = settings.AWS_S3_PRESIGNED_EXPIRATION
    params = {
        "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
        "Key": clave_objeto,
    }
    if nombre_archivo:
        from urllib.parse import quote
        params["ResponseContentDisposition"] = f'attachment; filename="{nombre_archivo}"; filename*=UTF-8\'\'{quote(nombre_archivo)}'
    else:
        params["ResponseContentDisposition"] = "attachment"

    return get_s3_client().generate_presigned_url(
        ClientMethod="get_object",
        Params=params,
        ExpiresIn=expiracion,
    )


def generar_url_previsualizacion(clave_objeto, content_type=None, expiracion=None):
    """Genera una URL prefirmada temporal para previsualizar el objeto en el navegador."""
    if expiracion is None:
        expiracion = settings.AWS_S3_PRESIGNED_EXPIRATION
    params = {
        "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
        "Key": clave_objeto,
        "ResponseContentDisposition": "inline",
    }
    if content_type:
        params["ResponseContentType"] = content_type

    return get_s3_client().generate_presigned_url(
        ClientMethod="get_object",
        Params=params,
        ExpiresIn=expiracion,
    )

