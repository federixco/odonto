"""Archivos DICOM, modelos 3D e imágenes que componen un estudio."""

from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.enums import CategoriaArchivo, EstadoArchivo, FormatoArchivo


# Metadatos del archivo almacenado y control de reemplazos/integridad.
class Archivo(models.Model):
    """Metadatos y ubicación de un archivo persistido."""

    # Durante la importación de una carpeta aún no existe el estudio definitivo:
    # el administrador primero revisa los datos detectados y luego lo confirma.
    estudio = models.ForeignKey(
        "estudios.Estudio",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="archivos",
        db_column="id_estudio",
    )
    # La importación existe antes que el estudio definitivo. Al confirmar,
    # ImportacionEstudio completa esta relación sin cambiar el modelo clínico.
    importacion = models.ForeignKey(
        "estudios.ImportacionEstudio",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="archivos",
        db_column="id_importacion",
    )
    nombre_archivo = models.CharField(max_length=255)
    # Ruta entregada por el navegador dentro de la carpeta seleccionada.
    ruta_relativa = models.CharField(max_length=500, blank=True, default="")
    formato = models.CharField(max_length=50, choices=FormatoArchivo.choices)
    categoria = models.CharField(max_length=30, choices=CategoriaArchivo.choices)
    # Guarda únicamente la clave privada del objeto, nunca una URL prefirmada.
    ruta_almacenamiento = models.CharField(max_length=500)
    tamano = models.PositiveBigIntegerField()
    hash_sha256 = models.CharField(max_length=64, null=True, blank=True)
    # El UID identifica una serie, no una instancia única: se indexa pero puede
    # repetirse entre muchos archivos de una misma tomografía.
    series_instance_uid = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
    )
    upload_id = models.CharField(max_length=255, null=True, blank=True)
    content_type = models.CharField(max_length=100, default="application/octet-stream")
    cantidad_partes = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=20, choices=EstadoArchivo.choices, default=EstadoArchivo.CARGANDO)
    archivo_reemplazado = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reemplazos", db_column="id_archivo_reemplazado")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "archivo"
        verbose_name = "archivo"
        verbose_name_plural = "archivos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(formato__in=FormatoArchivo.values),
                name="ck_archivo_formato_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(categoria__in=CategoriaArchivo.values),
                name="ck_archivo_categoria_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=EstadoArchivo.values),
                name="ck_archivo_estado_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad_partes__gte=1),
                name="ck_archivo_cantidad_partes_positiva",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(importacion__isnull=True)
                    | ~models.Q(ruta_relativa="")
                ),
                name="ck_archivo_importado_con_ruta",
            ),
            models.UniqueConstraint(
                fields=["importacion", "ruta_relativa"],
                name="uq_archivo_importacion_ruta",
            ),
        ]

    def __str__(self):
        return self.nombre_archivo

    def _normalizar_ruta_relativa(self):
        """Normaliza una ruta segura que no sale de la carpeta importada."""

        if self.ruta_relativa:
            ruta_normalizada = self.ruta_relativa.replace("\\", "/")
            ruta = PurePosixPath(ruta_normalizada)
            es_ruta_windows_absoluta = bool(ruta.parts and ":" in ruta.parts[0])
            if ruta.is_absolute() or es_ruta_windows_absoluta or ".." in ruta.parts:
                raise ValidationError(
                    {"ruta_relativa": "La ruta debe permanecer dentro de la carpeta importada."}
                )
            self.ruta_relativa = ruta.as_posix()
        elif self.importacion_id:
            raise ValidationError(
                {"ruta_relativa": "Un archivo importado debe conservar su ruta relativa."}
            )

    def clean(self):
        """Valida que la ruta sea relativa y permanezca en su carpeta."""

        super().clean()
        self._normalizar_ruta_relativa()

    def save(self, *args, **kwargs):
        """Normaliza la ruta antes de persistir el archivo."""

        self._normalizar_ruta_relativa()
        super().save(*args, **kwargs)

    def verificar_integridad(self):
        """Comprueba que el hash SHA-256 del archivo físico coincida con la base de datos."""
        if self.estado != EstadoArchivo.COMPLETO or not self.hash_sha256:
            return False

        from .services.storage import calcular_sha256_objeto

        return calcular_sha256_objeto(self.ruta_almacenamiento) == self.hash_sha256

