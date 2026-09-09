"""Servicios para interactuar con S3/MinIO mediante boto3."""

import os
import boto3
from django.conf import settings
from botocore.config import Config
from botocore.exceptions import ClientError

def get_s3_client():
    """Devuelve un cliente boto3 configurado para S3 o MinIO."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version="s3v4")
    )

def iniciar_multipart_upload(clave_objeto, content_type="application/octet-stream"):
    """Inicia una carga multipartes en S3 y devuelve el upload_id."""
    s3 = get_s3_client()
    respuesta = s3.create_multipart_upload(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=clave_objeto,
        ContentType=content_type
    )
    return respuesta["UploadId"]

def generar_urls_prefirmadas(clave_objeto, upload_id, cantidad_partes, expiracion=3600):
    """Genera las URLs prefirmadas para cada parte de la carga."""
    s3 = get_s3_client()
    urls = []
    for parte_numero in range(1, cantidad_partes + 1):
        url = s3.generate_presigned_url(
            ClientMethod="upload_part",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": clave_objeto,
                "UploadId": upload_id,
                "PartNumber": parte_numero,
            },
            ExpiresIn=expiracion
        )
        urls.append({
            "part_number": parte_numero,
            "url": url
        })
    return urls

def completar_multipart_upload(clave_objeto, upload_id, partes):
    """
    Completa la carga en S3 uniendo las partes.
    `partes` debe ser una lista de dicts: [{'PartNumber': 1, 'ETag': '"..."'}, ...]
    Devuelve los metadatos finales del objeto (incluyendo Size).
    """
    s3 = get_s3_client()
    
    # 1. Completar la carga
    s3.complete_multipart_upload(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=clave_objeto,
        UploadId=upload_id,
        MultipartUpload={"Parts": partes}
    )
    
    # 2. Consultar HEAD para obtener el tamano real y el checksum/ETag final
    head = s3.head_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=clave_objeto
    )
    
    return {
        "tamano": head["ContentLength"],
        "etag": head["ETag"].strip('"')
    }

def abortar_multipart_upload(clave_objeto, upload_id):
    """Aborta una carga multipartes incompleta, liberando espacio en S3."""
    s3 = get_s3_client()
    try:
        s3.abort_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=clave_objeto,
            UploadId=upload_id
        )
        return True
    except ClientError:
        return False
