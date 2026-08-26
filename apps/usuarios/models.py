"""Cuenta de usuario y perfil profesional del odontólogo."""

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.enums import EstadoCuenta, RolUsuario


# Cuenta central de autenticación: el rol define si pertenece al centro,
# a un odontólogo derivante o a un paciente con acceso excepcional.
class Usuario(AbstractUser):
    """Cuenta autenticable con uno de los tres roles del sistema."""

    username = models.CharField("nombre de usuario", max_length=50, unique=True)
    email = models.EmailField("correo electrónico", unique=True)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    rol = models.CharField(max_length=20, choices=RolUsuario.choices, default=RolUsuario.PACIENTE)
    estado = models.CharField(max_length=20, choices=EstadoCuenta.choices, default=EstadoCuenta.PENDIENTE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        """Alinea el superusuario de Django con el administrador del centro."""
        if self.is_superuser:
            self.is_staff = True
            self.rol = RolUsuario.ADMINISTRADOR
            self.estado = EstadoCuenta.HABILITADA
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
