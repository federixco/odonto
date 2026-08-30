"""Enumeraciones compartidas por los modelos del sistema."""

from django.db import models


class RolUsuario(models.TextChoices):
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
    ODONTOLOGO = "ODONTOLOGO", "Odontólogo"
    PACIENTE = "PACIENTE", "Paciente"


class EstadoCuenta(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    HABILITADA = "HABILITADA", "Habilitada"
    DESHABILITADA = "DESHABILITADA", "Deshabilitada"


class EstadoEstudio(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"
    PUBLICADO = "PUBLICADO", "Publicado"
    EN_REVISION = "EN_REVISION", "En revisión"
    ELIMINADO = "ELIMINADO", "Eliminado"


class EstadoArchivo(models.TextChoices):
    CARGANDO = "CARGANDO", "Cargando"
    COMPLETO = "COMPLETO", "Completo"
    INCORRECTO = "INCORRECTO", "Incorrecto"
    REEMPLAZADO = "REEMPLAZADO", "Reemplazado"


class EstadoAcceso(models.TextChoices):
    VIGENTE = "VIGENTE", "Vigente"
    REVOCADO = "REVOCADO", "Revocado"


class CategoriaArchivo(models.TextChoices):
    DICOM = "DICOM", "DICOM"
    MODELO_3D = "MODELO_3D", "Modelo 3D"
    IMAGEN_DOCUMENTO = "IMAGEN_DOCUMENTO", "Imagen o documento"
    PAQUETE_PROPIETARIO = "PAQUETE_PROPIETARIO", "Paquete propietario"


class FormatoArchivo(models.TextChoices):
    DICOM = "DICOM", "DICOM"
    STL = "STL", "STL"
    PLY = "PLY", "PLY"
    JPG = "JPG", "JPG"
    PNG = "PNG", "PNG"
    TIFF = "TIFF", "TIFF"
    PDF = "PDF", "PDF"
    GALILEOS = "GALILEOS", "Galileos"
    SIDEXIS = "SIDEXIS", "Sidexis"
    OTRO = "OTRO", "Otro"


class TipoEvento(models.TextChoices):
    INICIO_SESION = "INICIO_SESION", "Inicio de sesión"
    CARGA = "CARGA", "Carga"
    PUBLICACION = "PUBLICACION", "Publicación"
    VISUALIZACION = "VISUALIZACION", "Visualización"
    DESCARGA = "DESCARGA", "Descarga"
    REVOCACION = "REVOCACION", "Revocación"
    CORRECCION = "CORRECCION", "Corrección"
    ELIMINACION = "ELIMINACION", "Eliminación"
    NOTIFICACION = "NOTIFICACION", "Notificación"
    MODIFICACION_USUARIO = "MODIFICACION_USUARIO", "Modificación de usuario"
