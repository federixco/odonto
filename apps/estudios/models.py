"""Estudio odontológico asociado obligatoriamente a un paciente."""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.enums import EstadoAcceso, EstadoArchivo, EstadoEstudio


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
        pass

    def marcar_en_revision(self):
        """Cambia el estado del estudio si hay archivos incorrectos o dudas clínicas."""
        pass

    def reemplazar_archivo(self, archivo_viejo_id, archivo_nuevo):
        """Asocia un archivo nuevo como reemplazo de uno incorrecto."""
        pass

    def notificar_destinatarios(self):
        """Envía alertas (ej. email) a los odontólogos autorizados tras la publicación."""
        pass

