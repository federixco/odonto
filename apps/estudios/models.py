"""Estudio odontológico asociado obligatoriamente a un paciente."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.enums import (
    EstadoAcceso,
    EstadoArchivo,
    EstadoEstudio,
    EstadoImportacion,
    FormatoImportacion,
    NivelConfianza,
    RolUsuario,
)


class EstudioQuerySet(models.QuerySet):
    """Convierte eliminaciones masivas en eliminaciones lógicas."""

    def delete(self):
        actualizados = self.exclude(estado=EstadoEstudio.ELIMINADO).update(
            estado=EstadoEstudio.ELIMINADO,
            updated_at=timezone.now(),
        )
        return actualizados, {self.model._meta.label: actualizados}


class Estudio(models.Model):
    """Conjunto de imágenes y archivos de un paciente."""

    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.PROTECT, related_name="estudios", db_column="id_paciente")
    tipo = models.CharField(max_length=100)
    fecha_estudio = models.DateField()
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=EstadoEstudio.choices, default=EstadoEstudio.BORRADOR)
    fecha_publicacion = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EstudioQuerySet.as_manager()

    class Meta:
        db_table = "estudio"
        verbose_name = "estudio"
        verbose_name_plural = "estudios"
        ordering = ["-fecha_estudio", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estado__in=EstadoEstudio.values),
                name="ck_estudio_estado_valido",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado=EstadoEstudio.PUBLICADO)
                    | models.Q(fecha_publicacion__isnull=False)
                ),
                name="ck_estudio_publicado_con_fecha",
            ),
        ]

    def __str__(self):
        return f"Estudio {self.pk} - {self.paciente}"

    def publicar(self):
        """Publica únicamente estudios completos y con destinatarios vigentes."""
        if self.pk is None:
            raise ValidationError(
                "El estudio debe guardarse antes de poder publicarse."
            )
        if not self.archivos.exists():
            raise ValidationError(
                "El estudio debe contener al menos un archivo para publicarse."
            )
        if self.archivos.exclude(estado=EstadoArchivo.COMPLETO).exists():
            raise ValidationError(
                "Todos los archivos deben estar completos antes de publicar."
            )
        if not self.autorizaciones.filter(
            estado_acceso=EstadoAcceso.VIGENTE
        ).exists():
            raise ValidationError(
                "El estudio necesita al menos un odontólogo autorizado."
            )

        self.estado = EstadoEstudio.PUBLICADO
        self.fecha_publicacion = timezone.now()
        self.full_clean()
        self.save(update_fields=["estado", "fecha_publicacion", "updated_at"])

    def delete(self, using=None, keep_parents=False):
        """Marca el estudio como eliminado sin borrar sus datos relacionados."""
        if self.estado != EstadoEstudio.ELIMINADO:
            self.estado = EstadoEstudio.ELIMINADO
            self.save(update_fields=["estado", "updated_at"])
            return 1, {self._meta.label: 1}
        return 0, {self._meta.label: 0}


    def validar_carga(self):
        """Verifica que todos los archivos requeridos se hayan subido correctamente."""
        return (
            self.pk is not None
            and self.archivos.exists()
            and not self.archivos.exclude(estado=EstadoArchivo.COMPLETO).exists()
        )

    def marcar_en_revision(self):
        """Cambia el estado del estudio si hay archivos incorrectos o dudas clínicas."""
        pass

    def reemplazar_archivo(self, archivo_viejo_id, archivo_nuevo):
        """Asocia un archivo nuevo como reemplazo de uno incorrecto."""
        pass

    def notificar_destinatarios(self):
        """Envía alertas (ej. email) a los odontólogos autorizados tras la publicación."""
        pass


class ImportacionEstudio(models.Model):
    """Carpeta de estudio desde su carga hasta la confirmación administrativa.

    Los datos detectados son únicamente candidatos obtenidos de la exportación.
    El paciente y el estudio definitivos se establecen cuando el administrador
    revisa y confirma la importación.
    """

    estudio = models.ForeignKey(
        Estudio,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="importaciones",
        db_column="id_estudio",
    )
    iniciada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="importaciones_iniciadas",
        db_column="id_usuario",
    )
    paciente_sugerido = models.ForeignKey(
        "pacientes.Paciente",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="importaciones_sugeridas",
        db_column="id_paciente_sugerido",
    )
    nombre_carpeta = models.CharField(max_length=255)
    formato_detectado = models.CharField(
        max_length=30,
        choices=FormatoImportacion.choices,
        default=FormatoImportacion.DESCONOCIDO,
    )
    software_origen = models.CharField(max_length=100, blank=True)
    estado = models.CharField(
        max_length=30,
        choices=EstadoImportacion.choices,
        default=EstadoImportacion.CARGANDO,
    )
    nivel_confianza = models.CharField(
        max_length=10,
        choices=NivelConfianza.choices,
        null=True,
        blank=True,
    )
    nombre_paciente_detectado = models.CharField(max_length=200, blank=True)
    identificador_paciente_detectado = models.CharField(max_length=100, blank=True)
    fecha_nacimiento_detectada = models.DateField(null=True, blank=True)
    fecha_estudio_detectada = models.DateField(null=True, blank=True)
    descripcion_detectada = models.CharField(max_length=255, blank=True)
    study_instance_uid = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
    )
    cantidad_archivos = models.PositiveIntegerField(default=0)
    tamano_total = models.PositiveBigIntegerField(default=0)
    advertencias = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalizada_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "importacion_estudio"
        verbose_name = "importación de estudio"
        verbose_name_plural = "importaciones de estudios"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estado__in=EstadoImportacion.values),
                name="ck_importacion_estado_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(formato_detectado__in=FormatoImportacion.values),
                name="ck_importacion_formato_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(nivel_confianza__isnull=True)
                    | models.Q(nivel_confianza__in=NivelConfianza.values)
                ),
                name="ck_importacion_confianza_valida",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado=EstadoImportacion.CONFIRMADA)
                    | models.Q(estudio__isnull=False)
                ),
                name="ck_importacion_confirmada_con_estudio",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado=EstadoImportacion.CONFIRMADA)
                    | ~models.Q(formato_detectado=FormatoImportacion.DESCONOCIDO)
                ),
                name="ck_importacion_confirmada_con_formato",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado=EstadoImportacion.CONFIRMADA)
                    | models.Q(finalizada_at__isnull=False)
                ),
                name="ck_importacion_confirmada_finalizada",
            ),
        ]

    def __str__(self):
        return f"Importación {self.pk or 'nueva'} - {self.nombre_carpeta}"

    def clean(self):
        """Garantiza que solo la cuenta administrativa origine el lote."""

        super().clean()
        if self.iniciada_por_id and self.iniciada_por.rol != RolUsuario.ADMINISTRADOR:
            raise ValidationError(
                {"iniciada_por": "Solo el administrador puede iniciar importaciones."}
            )

    def esta_completa(self):
        """Comprueba cantidad, tamaño y estado de todos los archivos esperados."""

        if self.pk is None or self.cantidad_archivos == 0:
            return False
        resumen = self.archivos.aggregate(
            cantidad=models.Count("id"),
            tamano=models.Sum("tamano"),
        )
        return bool(
            resumen["cantidad"] == self.cantidad_archivos
            and resumen["tamano"] == self.tamano_total
            and not self.archivos.exclude(estado=EstadoArchivo.COMPLETO).exists()
        )

    def marcar_procesando(self):
        """Inicia el análisis solamente después de completar todas las cargas."""

        if not self.esta_completa():
            raise ValidationError(
                "La importación tiene archivos incompletos y no puede procesarse."
            )
        self.estado = EstadoImportacion.PROCESANDO
        self.save(update_fields=["estado", "updated_at"])

    def marcar_pendiente_confirmacion(self):
        """Expone el resultado detectado para que el administrador lo revise."""

        if self.estado != EstadoImportacion.PROCESANDO:
            raise ValidationError(
                "Solo una importación en procesamiento puede quedar pendiente."
            )
        self.estado = EstadoImportacion.PENDIENTE_CONFIRMACION
        self.save(update_fields=["estado", "updated_at"])

    def confirmar(self, estudio):
        """Vincula el estudio validado y finaliza la importación."""

        if estudio.pk is None:
            raise ValidationError("El estudio debe estar guardado antes de confirmar.")
        if self.estado != EstadoImportacion.PENDIENTE_CONFIRMACION:
            raise ValidationError(
                "La importación debe estar pendiente de confirmación."
            )
        if not self.esta_completa():
            raise ValidationError(
                "No se puede confirmar una importación con archivos incompletos."
            )
        with transaction.atomic():
            # Conservamos la importación como trazabilidad y además vinculamos
            # sus archivos al estudio, para que el resto del sistema continúe
            # usando la relación Estudio -> Archivo ya existente.
            self.archivos.update(estudio=estudio)
            self.estudio = estudio
            self.estado = EstadoImportacion.CONFIRMADA
            self.finalizada_at = timezone.now()
            self.full_clean()
            self.save(
                update_fields=[
                    "estudio",
                    "estado",
                    "finalizada_at",
                    "updated_at",
                ]
            )
        return estudio

    def cancelar(self):
        """Finaliza una importación descartada sin borrar su trazabilidad."""

        self.estado = EstadoImportacion.CANCELADA
        self.finalizada_at = timezone.now()
        self.save(update_fields=["estado", "finalizada_at", "updated_at"])

    def marcar_error(self, advertencia=None):
        """Registra un fallo de procesamiento conservando la importación."""

        if advertencia:
            self.advertencias = [*self.advertencias, str(advertencia)]
        self.estado = EstadoImportacion.ERROR
        self.finalizada_at = timezone.now()
        self.save(
            update_fields=[
                "advertencias",
                "estado",
                "finalizada_at",
                "updated_at",
            ]
        )


class SerieDicom(models.Model):
    """Agrupación de instancias DICOM pertenecientes a una importación."""

    importacion = models.ForeignKey(
        ImportacionEstudio,
        on_delete=models.PROTECT,
        related_name="series_dicom",
        db_column="id_importacion",
    )
    series_instance_uid = models.CharField(max_length=64)
    modalidad = models.CharField(max_length=16, blank=True)
    descripcion = models.CharField(max_length=255, blank=True)
    numero_serie = models.IntegerField(null=True, blank=True)
    cantidad_archivos = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "serie_dicom"
        verbose_name = "serie DICOM"
        verbose_name_plural = "series DICOM"
        constraints = [
            models.UniqueConstraint(
                fields=["importacion", "series_instance_uid"],
                name="uq_serie_dicom_importacion_uid",
            ),
        ]

    def __str__(self):
        return f"Serie {self.series_instance_uid}"

    def actualizar_cantidad_archivos(self):
        """Sincroniza el resumen con las instancias vinculadas a la serie."""

        self.cantidad_archivos = self.archivos.count()
        self.save(update_fields=["cantidad_archivos"])
        return self.cantidad_archivos

