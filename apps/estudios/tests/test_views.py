"""Pruebas del inicio administrativo de un estudio."""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.accesos.models import Autorizacion
from apps.archivos.models import Archivo
from apps.auditoria.models import LogActividad
from apps.core.enums import (
    CategoriaArchivo,
    EstadoArchivo,
    EstadoAcceso,
    EstadoCuenta,
    EstadoEstudio,
    EstadoImportacion,
    FormatoArchivo,
    RolUsuario,
    TipoEvento,
)
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo, Usuario

from ..models import Estudio, ImportacionEstudio


class EstudioViewsTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin_estudios",
            email="admin.estudios@example.com",
            password="Clave-Segura-2026!",
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odontologo = Usuario.objects.create_user(
            username="odontologo_estudios",
            email="odontologo.estudios@example.com",
            password="Clave-Segura-2026!",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.derivante = Odontologo.objects.create(
            usuario=self.odontologo,
            nombre="Ana",
            apellido="Torres",
            matricula="MP-1234",
        )
        self.paciente = Paciente.objects.create(
            nombre="María",
            apellido="Gómez",
            dni="30111222",
        )

    def test_administrador_puede_abrir_formulario(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("estudio_crear"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preparar un")

    def test_odontologo_no_puede_crear_estudio(self):
        self.client.force_login(self.odontologo)
        response = self.client.get(reverse("estudio_crear"))
        self.assertEqual(response.status_code, 403)

    def test_creacion_conserva_borrador_y_redirige_a_carga(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("estudio_crear"),
            {
                "paciente": self.paciente.pk,
                "tipo": "Tomografía 3D",
                "fecha_estudio": "2026-09-08",
                "observaciones": "Prueba sin datos clínicos reales.",
            },
        )
        estudio = Estudio.objects.get()
        self.assertEqual(estudio.estado, EstadoEstudio.BORRADOR)
        self.assertRedirects(response, reverse("estudio_detalle", args=[estudio.pk]))

    def test_detalle_resume_estudio_y_oculta_archivos_bajo_demanda(self):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
        )
        Archivo.objects.create(
            estudio=estudio,
            nombre_archivo="serie-001.dcm",
            ruta_relativa="DICOM/serie-001.dcm",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="estudios/prueba/serie-001.dcm",
            tamano=2048,
            hash_sha256="a" * 64,
            estado=EstadoArchivo.COMPLETO,
        )
        Autorizacion.objects.create(estudio=estudio, odontologo=self.derivante)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("estudio_detalle", args=[estudio.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mostrar detalles y archivos del estudio")
        self.assertContains(response, "serie-001.dcm")
        self.assertContains(response, "Accesos de odontólogos")
        self.assertContains(response, "Torres, Ana")

    def test_administrador_otorga_revoca_y_reactiva_acceso(self):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
        )
        self.client.force_login(self.admin)

        otorgar = self.client.post(
            reverse("estudio_acceso_agregar", args=[estudio.pk]),
            {"odontologo": self.derivante.pk},
        )
        autorizacion = Autorizacion.objects.get(
            estudio=estudio,
            odontologo=self.derivante,
        )
        self.assertRedirects(otorgar, reverse("estudio_detalle", args=[estudio.pk]))
        self.assertEqual(autorizacion.estado_acceso, EstadoAcceso.VIGENTE)

        revocar = self.client.post(
            reverse(
                "estudio_acceso_revocar",
                args=[estudio.pk, autorizacion.pk],
            )
        )
        autorizacion.refresh_from_db()
        self.assertRedirects(revocar, reverse("estudio_detalle", args=[estudio.pk]))
        self.assertEqual(autorizacion.estado_acceso, EstadoAcceso.REVOCADO)
        self.assertEqual(autorizacion.revocado_por, self.admin)
        self.assertIsNotNone(autorizacion.fecha_revocacion)

        reactivar = self.client.post(
            reverse("estudio_acceso_agregar", args=[estudio.pk]),
            {"odontologo": self.derivante.pk},
        )
        autorizacion.refresh_from_db()
        self.assertRedirects(reactivar, reverse("estudio_detalle", args=[estudio.pk]))
        self.assertEqual(autorizacion.estado_acceso, EstadoAcceso.VIGENTE)
        self.assertIsNone(autorizacion.revocado_por)
        self.assertIsNone(autorizacion.fecha_revocacion)

    def test_odontologo_no_puede_administrar_accesos(self):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
        )
        self.client.force_login(self.odontologo)

        response = self.client.post(
            reverse("estudio_acceso_agregar", args=[estudio.pk]),
            {"odontologo": self.derivante.pk},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Autorizacion.objects.exists())

    def test_post_no_autoriza_odontologo_deshabilitado(self):
        cuenta_deshabilitada = Usuario.objects.create_user(
            username="odontologo_deshabilitado",
            email="odontologo.deshabilitado@example.com",
            password="Clave-Segura-2026!",
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.DESHABILITADA,
        )
        odontologo_deshabilitado = Odontologo.objects.create(
            usuario=cuenta_deshabilitada,
            nombre="Diego",
            apellido="Inactivo",
            matricula="MP-9999",
        )
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("estudio_acceso_agregar", args=[estudio.pk]),
            {"odontologo": odontologo_deshabilitado.pk},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            Autorizacion.objects.filter(
                estudio=estudio,
                odontologo=odontologo_deshabilitado,
            ).exists()
        )

    def test_post_repetido_no_duplica_autorizacion(self):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
        )
        self.client.force_login(self.admin)
        url = reverse("estudio_acceso_agregar", args=[estudio.pk])

        primera = self.client.post(url, {"odontologo": self.derivante.pk})
        segunda = self.client.post(url, {"odontologo": self.derivante.pk})

        self.assertRedirects(primera, reverse("estudio_detalle", args=[estudio.pk]))
        self.assertRedirects(segunda, reverse("estudio_detalle", args=[estudio.pk]))
        self.assertEqual(
            Autorizacion.objects.filter(
                estudio=estudio,
                odontologo=self.derivante,
            ).count(),
            1,
        )

    def test_carga_rapida_es_la_pantalla_principal_y_muestra_recientes(self):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("importacion_crear"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Soltá aquí la carpeta del paciente")
        self.assertContains(response, "Seleccionar carpeta")
        self.assertContains(response, "No tenés que cargar los datos a mano")
        self.assertContains(response, "Gómez, María")
        self.assertContains(response, reverse("estudio_detalle", args=[estudio.pk]))

    def test_confirmacion_prioriza_datos_detectados_y_oculta_edicion(self):
        importacion = ImportacionEstudio.objects.create(
            iniciada_por=self.admin,
            paciente_sugerido=self.paciente,
            nombre_carpeta="GOMEZ_MARIA",
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
            cantidad_archivos=12,
            tamano_total=4096,
            datos_detectados={
                "formato": "DICOM",
                "fecha_estudio": "2026-09-12",
                "software_origen": "SIDEXIS",
            },
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("importacion_detalle", args=[importacion.pk])
        )

        self.assertContains(response, "Datos encontrados automáticamente")
        self.assertContains(response, "Gómez, María")
        self.assertContains(response, "Confirmar estudio")
        self.assertContains(response, "¿Hay un dato incorrecto?")
        self.assertContains(response, "Corregir paciente o datos detectados")
        self.assertContains(response, "Elegí el odontólogo derivante")
        self.assertContains(response, "Nombre, apellido, matrícula o correo")
        self.assertContains(response, "Torres, Ana")
        contenido = response.content.decode()
        self.assertLess(
            contenido.index("¿Hay un dato incorrecto?"),
            contenido.index("Elegí el odontólogo derivante"),
        )
        self.assertNotContains(response, '<details class="detected-edit" open>')

    def _crear_importacion_confirmable(self, nombre_carpeta):
        importacion = ImportacionEstudio.objects.create(
            iniciada_por=self.admin,
            paciente_sugerido=self.paciente,
            nombre_carpeta=nombre_carpeta,
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
            cantidad_archivos=1,
            tamano_total=128,
            datos_detectados={"formato": "DICOM", "fecha_estudio": "2026-09-12"},
        )
        Archivo.objects.create(
            importacion=importacion,
            nombre_archivo="imagen.dcm",
            ruta_relativa=f"{nombre_carpeta}/imagen.dcm",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="importaciones/prueba/imagen.dcm",
            tamano=128,
            hash_sha256="0" * 64,
            estado=EstadoArchivo.COMPLETO,
        )
        return importacion

    def test_confirmacion_sin_derivante_crea_borrador(self):
        importacion = self._crear_importacion_confirmable("GOMEZ_MARIA_BORRADOR")
        datos = {
            "paciente": self.paciente.pk,
            "tipo": "DICOM",
            "fecha_estudio": "2026-09-12",
            "observaciones": "",
        }
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("importacion_confirmar", args=[importacion.pk]),
            datos,
        )

        estudio = Estudio.objects.get()
        self.assertRedirects(
            response,
            reverse("estudio_detalle", args=[estudio.pk]),
        )
        self.assertEqual(estudio.estado, EstadoEstudio.BORRADOR)
        self.assertFalse(Autorizacion.objects.filter(estudio=estudio).exists())

    def test_confirmacion_con_derivante_crea_autorizacion_y_publica(self):
        importacion = self._crear_importacion_confirmable("GOMEZ_MARIA_PUBLICADO")
        datos = {
            "paciente": self.paciente.pk,
            "tipo": "DICOM",
            "fecha_estudio": "2026-09-12",
            "observaciones": "",
            "derivante": self.derivante.pk,
        }
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("importacion_confirmar", args=[importacion.pk]),
            datos,
        )

        estudio = Estudio.objects.get()
        self.assertRedirects(
            response,
            reverse("estudio_detalle", args=[estudio.pk]),
        )
        self.assertEqual(estudio.estado, EstadoEstudio.PUBLICADO)
        self.assertTrue(
            Autorizacion.objects.filter(
                estudio=estudio,
                odontologo=self.derivante,
            ).exists()
        )

    def test_sin_coincidencia_muestra_alta_paciente_ya_completada(self):
        importacion = ImportacionEstudio.objects.create(
            iniciada_por=self.admin,
            nombre_carpeta="PEREZ_JUAN",
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
            cantidad_archivos=8,
            tamano_total=2048,
            datos_detectados={
                "nombre_paciente": "PEREZ JUAN",
                "identificador_paciente": "33444555",
                "fecha_nacimiento": "1980-04-03",
                "formato": "DICOM",
            },
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("importacion_detalle", args=[importacion.pk])
        )

        self.assertContains(response, "No encontramos una ficha coincidente")
        self.assertContains(response, 'value="JUAN"')
        self.assertContains(response, 'value="PEREZ"')
        self.assertContains(response, 'value="33444555"')
        self.assertContains(response, "Crear paciente y continuar")

    def test_eliminacion_logica_revoca_acceso_y_conserva_archivos(self):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
            estado=EstadoEstudio.PUBLICADO,
            fecha_publicacion="2026-09-12T12:00:00Z",
        )
        archivo = Archivo.objects.create(
            estudio=estudio,
            nombre_archivo="serie-001.dcm",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="estudios/prueba/serie-001.dcm",
            tamano=2048,
            hash_sha256="f" * 64,
            estado=EstadoArchivo.COMPLETO,
        )
        autorizacion = Autorizacion.objects.create(
            estudio=estudio,
            odontologo=self.derivante,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("estudio_eliminar", args=[estudio.pk]),
            {"motivo": "Duplicado confirmado por el centro."},
        )

        self.assertRedirects(response, reverse("estudio_detalle", args=[estudio.pk]))
        estudio.refresh_from_db()
        autorizacion.refresh_from_db()
        self.assertEqual(estudio.estado, EstadoEstudio.ELIMINADO)
        self.assertEqual(estudio.eliminado_por, self.admin)
        self.assertEqual(estudio.motivo_eliminacion, "Duplicado confirmado por el centro.")
        self.assertIsNotNone(estudio.fecha_eliminacion)
        self.assertEqual(autorizacion.estado_acceso, EstadoAcceso.REVOCADO)
        self.assertTrue(Archivo.objects.filter(pk=archivo.pk).exists())
        self.assertTrue(
            LogActividad.objects.filter(
                estudio=estudio,
                tipo_evento=TipoEvento.ELIMINACION,
                resultado="Estudio eliminado lógicamente",
            ).exists()
        )

    @patch("apps.estudios.views.eliminar_objeto")
    def test_purga_fisica_borra_objetos_y_conserva_metadatos(self, eliminar):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
            estado=EstadoEstudio.ELIMINADO,
            fecha_eliminacion="2026-09-13T12:00:00Z",
            eliminado_por=self.admin,
            motivo_eliminacion="Sin espacio en almacenamiento.",
        )
        archivo = Archivo.objects.create(
            estudio=estudio,
            nombre_archivo="serie-001.dcm",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="estudios/prueba/serie-001.dcm",
            tamano=2048,
            hash_sha256="1" * 64,
            estado=EstadoArchivo.COMPLETO,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("estudio_purgar", args=[estudio.pk]),
            {"confirmacion": f"ELIMINAR ESTUDIO {estudio.pk}"},
        )

        self.assertRedirects(response, reverse("estudio_detalle", args=[estudio.pk]))
        eliminar.assert_called_once_with(archivo.ruta_almacenamiento)
        archivo.refresh_from_db()
        estudio.refresh_from_db()
        self.assertEqual(archivo.estado, EstadoArchivo.PURGADO)
        self.assertEqual(archivo.hash_sha256, "1" * 64)
        self.assertTrue(Estudio.objects.filter(pk=estudio.pk).exists())
        self.assertTrue(Archivo.objects.filter(pk=archivo.pk).exists())

    @patch("apps.estudios.views.eliminar_objeto")
    def test_purga_requiere_confirmacion_exacta(self, eliminar):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
            estado=EstadoEstudio.ELIMINADO,
            fecha_eliminacion="2026-09-13T12:00:00Z",
        )
        archivo = Archivo.objects.create(
            estudio=estudio,
            nombre_archivo="serie-001.dcm",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="estudios/prueba/serie-001.dcm",
            tamano=2048,
            hash_sha256="2" * 64,
            estado=EstadoArchivo.COMPLETO,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("estudio_purgar", args=[estudio.pk]),
            {"confirmacion": "ELIMINAR"},
        )

        self.assertRedirects(response, reverse("estudio_detalle", args=[estudio.pk]))
        eliminar.assert_not_called()
        archivo.refresh_from_db()
        self.assertEqual(archivo.estado, EstadoArchivo.COMPLETO)

    def test_estudio_purgado_no_muestra_boton_de_eliminacion_fisica(self):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
            estado=EstadoEstudio.ELIMINADO,
            fecha_eliminacion="2026-09-13T12:00:00Z",
            eliminado_por=self.admin,
            motivo_eliminacion="Purga terminada.",
        )
        Archivo.objects.create(
            estudio=estudio,
            nombre_archivo="serie-001.dcm",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="estudios/prueba/serie-001.dcm",
            tamano=2048,
            hash_sha256="3" * 64,
            estado=EstadoArchivo.PURGADO,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("estudio_detalle", args=[estudio.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Eliminar archivos definitivamente")
        self.assertNotContains(response, reverse("estudio_purgar", args=[estudio.pk]))
        self.assertContains(response, "Los archivos físicos ya fueron eliminados")

    def test_odontologo_no_puede_eliminar_ni_purgar_estudios(self):
        estudio = Estudio.objects.create(
            paciente=self.paciente,
            tipo="Tomografía 3D",
            fecha_estudio="2026-09-12",
        )
        self.client.force_login(self.odontologo)

        eliminar_response = self.client.post(
            reverse("estudio_eliminar", args=[estudio.pk]),
            {"motivo": "Intento no autorizado"},
        )

        self.assertEqual(eliminar_response.status_code, 403)
        estudio.refresh_from_db()
        self.assertEqual(estudio.estado, EstadoEstudio.BORRADOR)
