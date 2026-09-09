"""Operaciones de bajo nivel sobre el almacenamiento privado S3/MinIO."""

import hashlib

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


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
            s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE},
        ),
    )


def iniciar_multipart_upload(clave_objeto, content_type="application/octet-stream"):
    """Inicia una carga multipartes y devuelve su identificador interno."""

    respuesta = get_s3_client().create_multipart_upload(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=clave_objeto,
        ContentType=content_type,
    )
    return respuesta["UploadId"]


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
    s3.complete_multipart_upload(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=clave_objeto,
        UploadId=upload_id,
        MultipartUpload={"Parts": partes},
    )
    head = s3.head_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=clave_objeto,
    )
    return {
        "tamano": head["ContentLength"],
        # En multipartes el ETag no equivale al SHA-256 del archivo completo.
        "etag": head.get("ETag", "").strip('"'),
    }


def calcular_sha256_objeto(clave_objeto):
    """Calcula el SHA-256 real leyendo el objeto por bloques, sin cargarlo en RAM."""

    respuesta = get_s3_client().get_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=clave_objeto,
    )
    cuerpo = respuesta["Body"]
    digest = hashlib.sha256()
    try:
        while bloque := cuerpo.read(settings.S3_HASH_CHUNK_SIZE):
            digest.update(bloque)
    finally:
        cuerpo.close()
    return digest.hexdigest()


def abortar_multipart_upload(clave_objeto, upload_id):
    """Aborta una carga incompleta y devuelve si S3 confirmó la operación."""

    try:
        get_s3_client().abort_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=clave_objeto,
            UploadId=upload_id,
        )
        return True
    except Exception:
        return False


def eliminar_objeto(clave_objeto):
    """Elimina un objeto inválido que llegó a completarse físicamente."""

    get_s3_client().delete_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=clave_objeto,
    )
