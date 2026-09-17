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
    RolUsuario,
)


class EstudioQuerySet(models.QuerySet):
    """Convierte eliminaciones masivas en eliminaciones lógicas."""

    def delete(self):
        actualizados = self.exclude(estado=EstadoEstudio.ELIMINADO).update(
            estado=EstadoEstudio.ELIMINADO,
            fecha_eliminacion=timezone.now(),
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
    fecha_eliminacion = models.DateTimeField(null=True, blank=True)
    eliminado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="estudios_eliminados",
    )
    motivo_eliminacion = models.TextField(blank=True)
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
        archivos_vigentes = self.archivos.exclude(
            estado__in=[EstadoArchivo.REEMPLAZADO, EstadoArchivo.PURGADO]
        )
        if not archivos_vigentes.exists():
            raise ValidationError(
                "El estudio debe contener al menos un archivo para publicarse."
            )
        if archivos_vigentes.exclude(estado=EstadoArchivo.COMPLETO).exists():
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

    def eliminar_logicamente(self, usuario=None, motivo=""):
        """Oculta el estudio conservando archivos, accesos e historial."""

        if self.estado != EstadoEstudio.ELIMINADO:
            self.estado = EstadoEstudio.ELIMINADO
            self.fecha_eliminacion = timezone.now()
            self.eliminado_por = usuario
            self.motivo_eliminacion = (motivo or "").strip()
            self.save(
                update_fields=[
                    "estado",
                    "fecha_eliminacion",
                    "eliminado_por",
                    "motivo_eliminacion",
                    "updated_at",
                ]
            )
            return 1, {self._meta.label: 1}
        return 0, {self._meta.label: 0}

    def delete(self, using=None, keep_parents=False):
        """Convierte cualquier eliminación ORM en una eliminación lógica."""

        return self.eliminar_logicamente()

    def validar_carga(self):
        """Verifica que todos los archivos requeridos se hayan subido correctamente."""
        archivos_vigentes = self.archivos.exclude(
            estado__in=[EstadoArchivo.REEMPLAZADO, EstadoArchivo.PURGADO]
        )
        return (
            self.pk is not None
            and archivos_vigentes.exists()
            and not archivos_vigentes.exclude(estado=EstadoArchivo.COMPLETO).exists()
        )

    def marcar_en_revision(self):
        """Cambia el estado del estudio si hay archivos incorrectos o dudas clínicas."""
        if self.estado == EstadoEstudio.ELIMINADO:
            raise ValidationError("Un estudio eliminado no puede entrar en revisión.")
        if self.estado != EstadoEstudio.EN_REVISION:
            self.estado = EstadoEstudio.EN_REVISION
            self.save(update_fields=["estado", "updated_at"])
        return self

    def reemplazar_archivo(self, archivo_viejo_id, archivo_nuevo):
        """Asocia un archivo nuevo como reemplazo de uno incorrecto."""
        if self.estado == EstadoEstudio.ELIMINADO:
            raise ValidationError("No se pueden reemplazar archivos de un estudio eliminado.")
        if not archivo_nuevo.pk or archivo_nuevo.estudio_id != self.pk:
            raise ValidationError("El archivo nuevo debe pertenecer a este estudio.")
        if archivo_nuevo.estado != EstadoArchivo.COMPLETO:
            raise ValidationError("El archivo nuevo debe estar completo.")

        with transaction.atomic():
            archivo_viejo = self.archivos.select_for_update().get(pk=archivo_viejo_id)
            if archivo_viejo.estado != EstadoArchivo.INCORRECTO:
                raise ValidationError("Solo se puede reemplazar un archivo incorrecto.")
            if archivo_nuevo.archivo_reemplazado_id not in {None, archivo_viejo.pk}:
                raise ValidationError("El archivo nuevo ya reemplaza a otro archivo.")

            archivo_nuevo.archivo_reemplazado = archivo_viejo
            archivo_nuevo.save(update_fields=["archivo_reemplazado", "updated_at"])
            archivo_viejo.estado = EstadoArchivo.REEMPLAZADO
            archivo_viejo.save(update_fields=["estado", "updated_at"])
        return archivo_nuevo

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
        on_delete=models.SET_NULL,
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
        on_delete=models.SET_NULL,
        related_name="importaciones_sugeridas",
        db_column="id_paciente_sugerido",
    )
    nombre_carpeta = models.CharField(max_length=255)
    estado = models.CharField(
        max_length=30,
        choices=EstadoImportacion.choices,
        default=EstadoImportacion.CARGANDO,
    )
    cantidad_archivos = models.PositiveIntegerField(default=0)
    tamano_total = models.PositiveBigIntegerField(default=0)
    # Resultado variable de detectar un paquete; siempre es una sugerencia.
    datos_detectados = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
                condition=(
                    ~models.Q(estado=EstadoImportacion.CONFIRMADA)
                    | models.Q(estudio__isnull=False)
                ),
                name="ck_importacion_confirmada_con_estudio",
            ),
        ]

    def __str__(self):
        return f"Importación {self.pk or 'nueva'} - {self.nombre_carpeta}"

    @property
    def advertencias(self):
        """Expone las advertencias del JSON sin duplicar columnas."""
        return (self.datos_detectados or {}).get("advertencias", [])

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
            self.full_clean()
            self.save(
                update_fields=[
                    "estudio",
                    "estado",
                    "updated_at",
                ]
            )
        return estudio

    def cancelar(self):
        """Finaliza una importación descartada sin borrar su trazabilidad."""

        self.estado = EstadoImportacion.CANCELADA
        self.save(update_fields=["estado", "updated_at"])

    def marcar_error(self, advertencia=None):
        """Registra un fallo de procesamiento conservando la importación."""

        datos = self.datos_detectados or {}
        if advertencia:
            datos["advertencias"] = [*datos.get("advertencias", []), str(advertencia)]
        self.datos_detectados = datos
        self.estado = EstadoImportacion.ERROR
        self.save(
            update_fields=[
                "datos_detectados",
                "estado",
                "updated_at",
            ]
        )
