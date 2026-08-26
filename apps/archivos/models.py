"""Archivos DICOM, modelos 3D e imágenes que componen un estudio."""

from django.db import models

from apps.core.enums import CategoriaArchivo, EstadoArchivo, FormatoArchivo


# Metadatos del archivo almacenado y control de reemplazos/integridad.
class Archivo(models.Model):
    """Metadatos y ubicación de un archivo persistido."""

    estudio = models.ForeignKey("estudios.Estudio", on_delete=models.CASCADE, related_name="archivos", db_column="id_estudio")
    nombre_archivo = models.CharField(max_length=255)
    formato = models.CharField(max_length=50, choices=FormatoArchivo.choices)
    categoria = models.CharField(max_length=30, choices=CategoriaArchivo.choices)
    ruta_almacenamiento = models.CharField(max_length=500)
    tamano = models.PositiveBigIntegerField()
    hash_sha256 = models.CharField(max_length=64)
    estado = models.CharField(max_length=20, choices=EstadoArchivo.choices, default=EstadoArchivo.CARGANDO)
    archivo_reemplazado = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reemplazos", db_column="id_archivo_reemplazado")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "archivo"
        verbose_name = "archivo"
        verbose_name_plural = "archivos"

    def __str__(self):
        return self.nombre_archivo
