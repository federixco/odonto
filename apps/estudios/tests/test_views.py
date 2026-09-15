"""Pruebas del inicio administrativo de un estudio."""

from django.test import TestCase
from django.urls import reverse

from apps.accesos.models import Autorizacion
from apps.archivos.models import Archivo
from apps.core.enums import (
    CategoriaArchivo,
    EstadoArchivo,
    EstadoAcceso,
    EstadoCuenta,
    EstadoEstudio,
    EstadoImportacion,
    FormatoArchivo,
    RolUsuario,
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

    def test_confirmacion_exige_derivante_y_crea_autorizacion(self):
        importacion = ImportacionEstudio.objects.create(
            iniciada_por=self.admin,
            paciente_sugerido=self.paciente,
            nombre_carpeta="GOMEZ_MARIA",
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
            cantidad_archivos=1,
            tamano_total=128,
            datos_detectados={"formato": "DICOM", "fecha_estudio": "2026-09-12"},
        )
        Archivo.objects.create(
            importacion=importacion,
            nombre_archivo="imagen.dcm",
            ruta_relativa="GOMEZ_MARIA/imagen.dcm",
            formato=FormatoArchivo.DICOM,
            categoria=CategoriaArchivo.DICOM,
            ruta_almacenamiento="importaciones/prueba/imagen.dcm",
            tamano=128,
            hash_sha256="0" * 64,
            estado=EstadoArchivo.COMPLETO,
        )
        datos = {
            "paciente": self.paciente.pk,
            "tipo": "DICOM",
            "fecha_estudio": "2026-09-12",
            "observaciones": "",
        }
        self.client.force_login(self.admin)

        sin_derivante = self.client.post(
            reverse("importacion_confirmar", args=[importacion.pk]),
            datos,
        )
        self.assertEqual(sin_derivante.status_code, 200)
        self.assertContains(sin_derivante, "Este campo es obligatorio")
        self.assertFalse(Estudio.objects.exists())

        con_derivante = self.client.post(
            reverse("importacion_confirmar", args=[importacion.pk]),
            {**datos, "derivante": self.derivante.pk},
        )

        estudio = Estudio.objects.get()
        self.assertRedirects(
            con_derivante,
            reverse("estudio_detalle", args=[estudio.pk]),
        )
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
