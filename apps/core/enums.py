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


class FormatoImportacion(models.TextChoices):
    """Formato global detectado al analizar una carpeta exportada."""

    DICOM = "DICOM", "DICOM"
    GALILEOS = "GALILEOS", "Galileos"
    STL = "STL", "STL"
    RADIOGRAFIA = "RADIOGRAFIA", "Radiografía"
    DESCONOCIDO = "DESCONOCIDO", "Desconocido"


class EstadoImportacion(models.TextChoices):
    """Etapas persistentes del procesamiento de una carpeta de estudio."""

    CARGANDO = "CARGANDO", "Cargando"
    PROCESANDO = "PROCESANDO", "Procesando"
    PENDIENTE_CONFIRMACION = "PENDIENTE_CONFIRMACION", "Pendiente de confirmación"
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    ERROR = "ERROR", "Error"
    CANCELADA = "CANCELADA", "Cancelada"


class NivelConfianza(models.TextChoices):
    """Confianza de una sugerencia automática; nunca sustituye la confirmación."""

    ALTA = "ALTA", "Alta"
    MEDIA = "MEDIA", "Media"
    BAJA = "BAJA", "Baja"


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
    IMPORTACION_INICIADA = "IMPORTACION_INICIADA", "Importación iniciada"
    DETECCION_COMPLETADA = "DETECCION_COMPLETADA", "Detección completada"
    IMPORTACION_CONFIRMADA = "IMPORTACION_CONFIRMADA", "Importación confirmada"
    IMPORTACION_CANCELADA = "IMPORTACION_CANCELADA", "Importación cancelada"
    ERROR_PROCESAMIENTO = "ERROR_PROCESAMIENTO", "Error de procesamiento"
