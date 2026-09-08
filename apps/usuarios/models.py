"""Cuenta de usuario y perfil profesional del odontólogo."""

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.enums import EstadoCuenta, RolUsuario


class Usuario(AbstractUser):
    """Cuenta autenticable con uno de los tres roles del sistema.

    Una cuenta puede utilizar correo electrónico, teléfono o ambos como medio
    de contacto. El estado funcional se sincroniza con ``is_active``, utilizado
    internamente por Django para permitir o rechazar la autenticación.
    """

    username = models.CharField("nombre de usuario", max_length=50, unique=True)
    email = models.EmailField("correo electrónico", unique=True, null=True, blank=True)
    telefono = models.CharField("teléfono", max_length=30, unique=True, null=True, blank=True)
    rol = models.CharField(max_length=20, choices=RolUsuario.choices, default=RolUsuario.PACIENTE)
    estado = models.CharField(max_length=20, choices=EstadoCuenta.choices, default=EstadoCuenta.PENDIENTE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(email__isnull=False) & ~models.Q(email=""))
                    | (models.Q(telefono__isnull=False) & ~models.Q(telefono=""))
                ),
                name="ck_usuario_medio_contacto",
            ),
            models.CheckConstraint(
                condition=models.Q(rol__in=RolUsuario.values),
                name="ck_usuario_rol_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=EstadoCuenta.values),
                name="ck_usuario_estado_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        estado=EstadoCuenta.HABILITADA,
                        is_active=True,
                    )
                    | models.Q(
                        estado__in=[
                            EstadoCuenta.PENDIENTE,
                            EstadoCuenta.DESHABILITADA,
                        ],
                        is_active=False,
                    )
                ),
                name="ck_usuario_estado_autenticacion",
            ),
        ]

    def __str__(self):
        return self.get_full_name() or self.username

    def _sincronizar_estado_autenticacion(self):
        """Mantiene coherentes el estado del dominio y los flags de Django."""
        if self.is_superuser:
            self.is_staff = True
            self.rol = RolUsuario.ADMINISTRADOR
            self.estado = EstadoCuenta.HABILITADA
            self.is_active = True
        else:
            self.is_active = self.estado == EstadoCuenta.HABILITADA

    def clean(self):
        """Normaliza y valida los medios de contacto de la cuenta."""
        self._sincronizar_estado_autenticacion()
        super().clean()
        self.email = self.email.strip().lower() if self.email else None
        self.telefono = self.telefono.strip() if self.telefono else None

        if not self.email and not self.telefono:
            raise ValidationError(
                "El usuario debe tener un correo electrónico o un teléfono."
            )

    def save(self, *args, **kwargs):
        """Sincroniza el estado funcional con la autenticación de Django."""
        campos_sincronizados = {"is_active"}

        self._sincronizar_estado_autenticacion()

        if self.is_superuser:
            campos_sincronizados.update({"is_staff", "rol", "estado"})

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | campos_sincronizados

        super().save(*args, **kwargs)


# Perfil profesional asociado a la cuenta del odontólogo derivante.
class Odontologo(models.Model):
    """Datos profesionales del odontólogo derivante."""

    usuario = models.OneToOneField("usuarios.Usuario", on_delete=models.CASCADE, related_name="odontologo", db_column="id_usuario")
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    matricula = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "odontologo"
        verbose_name = "odontólogo"
        verbose_name_plural = "odontólogos"

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"


    def consultar_pacientes_autorizados(self):
        """Devuelve la lista de pacientes que han autorizado a este odontólogo."""
        pass

    def consultar_estudio(self, estudio_id):
        """Devuelve un estudio específico si el odontólogo tiene autorización."""
        pass

    def visualizar_estudio(self, estudio_id):
        """Registra la visualización y devuelve la URL del visor para el estudio."""
        pass

    def descargar_estudio(self, estudio_id):
        """Registra la descarga y devuelve el archivo comprimido del estudio."""
        pass

