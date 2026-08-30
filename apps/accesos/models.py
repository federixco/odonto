"""Autorizaciones temporales o revocables para compartir estudios."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.enums import EstadoAcceso, EstadoEstudio, RolUsuario


# Permiso revocable mediante el cual un odontólogo recibe un estudio.
class Autorizacion(models.Model):
    """Permiso de un odontólogo para acceder a un estudio.

    Una autorización vigente no contiene datos de revocación. Al revocarla se
    conservan obligatoriamente la fecha y el administrador responsable.
    """

    odontologo = models.ForeignKey("usuarios.Odontologo", on_delete=models.PROTECT, related_name="autorizaciones", db_column="id_odontologo")
    estudio = models.ForeignKey("estudios.Estudio", on_delete=models.PROTECT, related_name="autorizaciones", db_column="id_estudio")
    estado_acceso = models.CharField(max_length=15, choices=EstadoAcceso.choices, default=EstadoAcceso.VIGENTE)
    fecha_autorizacion = models.DateTimeField(auto_now_add=True)
    fecha_revocacion = models.DateTimeField(null=True, blank=True)
    revocado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="autorizaciones_revocadas")

    class Meta:
        db_table = "autorizacion"
        verbose_name = "autorización"
        verbose_name_plural = "autorizaciones"
        constraints = [
            models.UniqueConstraint(
                fields=["odontologo", "estudio"],
                name="uq_autorizacion_odontologo_estudio",
            ),
            models.CheckConstraint(
                condition=models.Q(estado_acceso__in=EstadoAcceso.values),
                name="ck_autorizacion_estado_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        estado_acceso=EstadoAcceso.VIGENTE,
                        fecha_revocacion__isnull=True,
                        revocado_por__isnull=True,
                    )
                    | models.Q(
                        estado_acceso=EstadoAcceso.REVOCADO,
                        fecha_revocacion__isnull=False,
                        revocado_por__isnull=False,
                    )
                ),
                name="ck_autorizacion_datos_revocacion",
            ),
        ]

    def clean(self):
        """Valida la coherencia del estado y el responsable de revocación."""
        super().clean()
        errores = {}

        if self.estado_acceso == EstadoAcceso.VIGENTE:
            if self.fecha_revocacion is not None:
                errores["fecha_revocacion"] = (
                    "Una autorización vigente no puede tener fecha de revocación."
                )
            if self.revocado_por_id is not None:
                errores["revocado_por"] = (
                    "Una autorización vigente no puede tener usuario revocador."
                )

        if self.estado_acceso == EstadoAcceso.REVOCADO:
            if self.fecha_revocacion is None:
                errores["fecha_revocacion"] = (
                    "Una autorización revocada debe indicar la fecha de revocación."
                )
            if self.revocado_por_id is None:
                errores["revocado_por"] = (
                    "Una autorización revocada debe indicar quién la revocó."
                )

        if (
            self.revocado_por_id is not None
            and self.revocado_por.rol != RolUsuario.ADMINISTRADOR
        ):
            errores["revocado_por"] = (
                "Solo el administrador puede revocar una autorización."
            )

        if errores:
            raise ValidationError(errores)

    def esta_vigente(self):
        return (
            self.estado_acceso == EstadoAcceso.VIGENTE
            and self.estudio.estado != EstadoEstudio.ELIMINADO
        )

    def revocar(self, usuario):
        """Revoca el acceso y conserva fecha y administrador responsable."""
        self.estado_acceso = EstadoAcceso.REVOCADO
        self.fecha_revocacion = timezone.now()
        self.revocado_por = usuario
        self.full_clean()
        self.save(update_fields=["estado_acceso", "fecha_revocacion", "revocado_por"])
