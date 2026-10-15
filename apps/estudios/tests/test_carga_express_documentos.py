"""Pruebas para la carga exprés de documentos sin paciente previo y gestión en el consultorio."""

import json
from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accesos.models import Autorizacion
from apps.archivos.models import Archivo
from apps.core.enums import (
    CategoriaArchivo,
    EstadoAcceso,
    EstadoArchivo,
    EstadoCuenta,
    EstadoEstudio,
    EstadoImportacion,
    FormatoArchivo,
    RolUsuario,
)
from apps.core.permisos_estudios import comprobar_acceso_estudio
from apps.estudios.models import Estudio, ImportacionEstudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo, Usuario


class CargaExpressDocumentosTests(TestCase):
    def setUp(self):
        self.password = "Clave-Segura-2026!"
        self.admin = Usuario.objects.create_user(
            username="admin_exp",
            email="admin.exp@example.com",
            password=self.password,
            rol=RolUsuario.ADMINISTRADOR,
            estado=EstadoCuenta.HABILITADA,
        )
        self.user_odo = Usuario.objects.create_user(
            username="odo_exp",
            email="odo.exp@example.com",
            password=self.password,
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
        )
        self.odontologo = Odontologo.objects.create(
            usuario=self.user_odo,
            nombre="Laura",
            apellido="Vázquez",
            matricula="MP-9988",
        )
        self.user_paciente = Usuario.objects.create_user(
            username="paciente_exp",
            email="paciente.exp@example.com",
            password=self.password,
            rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente_real = Paciente.objects.create(
            usuario=self.user_paciente,
            nombre="Carlos",
            apellido="Benítez",
            dni="35123456",
        )

    def test_confirmar_express_crea_estudio_privado_y_autorizacion(self):
        """Al arrastrar directo al odontólogo, se confirma express con paciente provisional TEMP-."""
        self.client.force_login(self.admin)
        lote = ImportacionEstudio.objects.create(
            iniciada_por=self.admin,
            nombre_carpeta="Informe_Periapical_Diente_16.pdf",
            cantidad_archivos=1,
            tamano_total=2048,
            estado=EstadoImportacion.CARGANDO,
        )
        Archivo.objects.create(
            importacion=lote,
            nombre_archivo="Informe_Periapical_Diente_16.pdf",
            ruta_relativa="Informe_Periapical_Diente_16.pdf",
            ruta_almacenamiento=f"importaciones/{lote.pk}/archivos/doc.pdf",
            tamano=2048,
            formato=FormatoArchivo.PDF,
            categoria=CategoriaArchivo.IMAGEN_DOCUMENTO,
            estado=EstadoArchivo.COMPLETO,
        )

        url = reverse("importacion_confirmar_express", args=[lote.pk])
        resp = self.client.post(
            url,
            data=json.dumps({"odontologo_id": self.odontologo.pk}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        datos = resp.json()
        self.assertEqual(datos["status"], "ok")

        lote.refresh_from_db()
        self.assertEqual(lote.estado, EstadoImportacion.CONFIRMADA)
        estudio = lote.estudio
        self.assertIsNotNone(estudio)
        self.assertEqual(estudio.tipo, "DOCUMENTO_PRIVADO")
        self.assertEqual(estudio.estado, EstadoEstudio.PUBLICADO)
        self.assertTrue(estudio.paciente.dni.startswith("TEMP-"))
        self.assertEqual(estudio.paciente.apellido, "Sin clasificar")

        # Autorización vigente para el odontólogo
        aut = Autorizacion.objects.filter(estudio=estudio, odontologo=self.odontologo).first()
        self.assertIsNotNone(aut)
        self.assertEqual(aut.estado_acceso, EstadoAcceso.VIGENTE)

    def test_documento_privado_no_es_accesible_por_paciente(self):
        """Los documentos privados están estrictamente bloqueados para cuentas de rol PACIENTE."""
        estudio_privado = Estudio.objects.create(
            paciente=self.paciente_real,
            tipo="DOCUMENTO_PRIVADO",
            fecha_estudio=timezone.now().date(),
            fecha_publicacion=timezone.now(),
            observaciones="[PRIVADO] Ficha interna clínica",
            estado=EstadoEstudio.PUBLICADO,
        )

        with self.assertRaises(PermissionDenied):
            comprobar_acceso_estudio(self.user_paciente, estudio_privado)

        # En el dashboard del paciente tampoco aparece
        self.client.force_login(self.user_paciente)
        resp = self.client.get(reverse("dashboard_paciente"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["estudios"]), 0)

    def test_odontologo_ve_documento_en_banner_sin_clasificar(self):
        """El odontólogo ve el documento recibido en su bandeja de entrada sin clasificar."""
        paciente_temp = Paciente.objects.create(
            nombre="Presupuesto_Implantologia",
            apellido="Sin clasificar",
            dni="TEMP-ABCD1234",
        )
        estudio = Estudio.objects.create(
            paciente=paciente_temp,
            tipo="DOCUMENTO_PRIVADO",
            fecha_estudio=timezone.now().date(),
            fecha_publicacion=timezone.now(),
            observaciones="[PRIVADO] Documento recibido directo",
            estado=EstadoEstudio.PUBLICADO,
        )
        Autorizacion.objects.create(
            estudio=estudio,
            odontologo=self.odontologo,
            estado_acceso=EstadoAcceso.VIGENTE,
        )

        self.client.force_login(self.user_odo)
        resp = self.client.get(reverse("dashboard_odontologo"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["estudios_sin_clasificar"]), 1)
        self.assertContains(resp, "Documentos recibidos sin clasificar")
        self.assertContains(resp, "Presupuesto_Implantologia")

    def test_odontologo_mueve_documento_a_paciente_existente(self):
        """El odontólogo mueve el documento a un paciente existente; el temporal se elimina."""
        paciente_temp = Paciente.objects.create(
            nombre="Radiografia_Sulta",
            apellido="Sin clasificar",
            dni="TEMP-REASIGN1",
        )
        estudio = Estudio.objects.create(
            paciente=paciente_temp,
            tipo="DOCUMENTO_PRIVADO",
            fecha_estudio=timezone.now().date(),
            fecha_publicacion=timezone.now(),
            observaciones="[PRIVADO] Documento suelto",
            estado=EstadoEstudio.PUBLICADO,
        )
        Autorizacion.objects.create(
            estudio=estudio,
            odontologo=self.odontologo,
            estado_acceso=EstadoAcceso.VIGENTE,
        )

        self.client.force_login(self.user_odo)
        url_mover = reverse("estudio_mover_paciente", args=[estudio.pk])
        resp = self.client.post(
            url_mover,
            data={
                "accion_paciente": "existente",
                "paciente_id": self.paciente_real.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)

        estudio.refresh_from_db()
        self.assertEqual(estudio.paciente, self.paciente_real)
        # El paciente provisional huérfano fue eliminado
        self.assertFalse(Paciente.objects.filter(pk=paciente_temp.pk).exists())

    def test_odontologo_mueve_documento_a_nuevo_paciente(self):
        """El odontólogo puede crear una nueva carpeta de paciente al mover el documento."""
        paciente_temp = Paciente.objects.create(
            nombre="Plan_Tratamiento",
            apellido="Sin clasificar",
            dni="TEMP-NUEVO01",
        )
        estudio = Estudio.objects.create(
            paciente=paciente_temp,
            tipo="DOCUMENTO_PRIVADO",
            fecha_estudio=timezone.now().date(),
            fecha_publicacion=timezone.now(),
            observaciones="[PRIVADO] Documento suelto",
            estado=EstadoEstudio.PUBLICADO,
        )
        Autorizacion.objects.create(
            estudio=estudio,
            odontologo=self.odontologo,
            estado_acceso=EstadoAcceso.VIGENTE,
        )

        self.client.force_login(self.user_odo)
        url_mover = reverse("estudio_mover_paciente", args=[estudio.pk])
        resp = self.client.post(
            url_mover,
            data={
                "accion_paciente": "nuevo",
                "nuevo_nombre": "Florencia",
                "nuevo_apellido": "Romero",
                "nuevo_dni": "39999888",
            },
        )
        self.assertEqual(resp.status_code, 302)

        nuevo_paciente = Paciente.objects.filter(dni="39999888").first()
        self.assertIsNotNone(nuevo_paciente)
        self.assertEqual(nuevo_paciente.apellido, "Romero")
        estudio.refresh_from_db()
        self.assertEqual(estudio.paciente, nuevo_paciente)

    def test_registrar_paciente_detectado_sin_dni_genera_temp(self):
        """Si el administrador no ingresa DNI para un archivo detectado (ej. STL), se genera TEMP-."""
        self.client.force_login(self.admin)
        lote = ImportacionEstudio.objects.create(
            iniciada_por=self.admin,
            nombre_carpeta="Mandibula_Alineador.stl",
            cantidad_archivos=1,
            tamano_total=1024,
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
            datos_detectados={"nombre_paciente": "Gomez Martin", "formato": "STL"},
        )
        url = reverse("importacion_registrar_paciente", args=[lote.pk])
        resp = self.client.post(
            url,
            data={
                "nombre": "Martin",
                "apellido": "Gomez",
                "dni": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        lote.refresh_from_db()
        self.assertIsNotNone(lote.paciente_sugerido)
        self.assertEqual(lote.paciente_sugerido.nombre, "Martin")
        self.assertEqual(lote.paciente_sugerido.apellido, "Gomez")
        self.assertTrue(lote.paciente_sugerido.dni.startswith("TEMP-"))

    def test_confirmar_express_preserva_nombre_detectado_stl(self):
        """En confirmación express con STL, el paciente provisional adopta el nombre detectado."""
        self.client.force_login(self.admin)
        lote = ImportacionEstudio.objects.create(
            iniciada_por=self.admin,
            nombre_carpeta="Gomez_Martin_Maxilar.stl",
            cantidad_archivos=1,
            tamano_total=2048,
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION,
            datos_detectados={"nombre_paciente": "Gomez Martin", "formato": "STL"},
        )
        Archivo.objects.create(
            importacion=lote,
            nombre_archivo="Gomez_Martin_Maxilar.stl",
            ruta_relativa="Gomez_Martin_Maxilar.stl",
            ruta_almacenamiento=f"importaciones/{lote.pk}/archivos/stl1.stl",
            tamano=2048,
            formato=FormatoArchivo.STL,
            categoria=CategoriaArchivo.MODELO_3D,
            estado=EstadoArchivo.COMPLETO,
        )
        url = reverse("importacion_confirmar_express", args=[lote.pk])
        resp = self.client.post(
            url,
            data=json.dumps({"odontologo_id": self.odontologo.pk}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        lote.refresh_from_db()
        estudio = lote.estudio
        self.assertIsNotNone(estudio)
        self.assertEqual(estudio.paciente.apellido, "Gomez")
        self.assertEqual(estudio.paciente.nombre, "Martin")
        self.assertTrue(estudio.paciente.dni.startswith("TEMP-"))

