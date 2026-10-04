"""Límites reales de las páginas y resúmenes sin precargar tomografías."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accesos.models import Autorizacion
from apps.archivos.models import Archivo
from apps.core.enums import CategoriaArchivo, EstadoArchivo, EstadoCuenta, EstadoEstudio, FormatoArchivo, RolUsuario
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo, Usuario


class PaginacionRecursosTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(username="admin_paginas", email="paginas@example.test", password="clave-test")
        self.paciente = Paciente.objects.create(nombre="Ana", apellido="Prueba", dni="30111222")
        self.client.force_login(self.admin)

    def estudio(self, **extra):
        if extra.get("estado") == EstadoEstudio.PUBLICADO:
            extra.setdefault("fecha_publicacion", timezone.now())
        return Estudio.objects.create(paciente=self.paciente, tipo="DICOM", fecha_estudio="2026-09-10", **extra)

    def archivos(self, estudio, cantidad):
        Archivo.objects.bulk_create([
            Archivo(estudio=estudio, nombre_archivo=f"{i:04}.dcm", ruta_relativa=f"carpeta/{i:04}.dcm",
                    formato=FormatoArchivo.DICOM, categoria=CategoriaArchivo.DICOM,
                    ruta_almacenamiento=f"pruebas/{estudio.pk}/{i}", tamano=1, estado=EstadoArchivo.COMPLETO)
            for i in range(cantidad)
        ])

    def test_listado_pacientes_limita_y_preserva_busqueda(self):
        Paciente.objects.bulk_create([Paciente(nombre="Paciente", apellido="Prueba", dni=str(71000000 + i)) for i in range(30)])
        response = self.client.get(reverse("paciente_lista"), {"q": "Prueba"})
        self.assertEqual(len(response.context["pacientes"]), 25)
        self.assertEqual(response.context["page_obj"].paginator.count, 31)
        self.assertContains(response, "q=Prueba&amp;page=2")
        segunda = self.client.get(reverse("paciente_lista"), {"q": "Prueba", "page": 2})
        self.assertEqual(len(segunda.context["pacientes"]), 6)

    def test_estudios_planos_y_agrupados_se_paginan(self):
        for _ in range(30):
            self.estudio()
        response = self.client.get(reverse("estudio_lista"))
        self.assertEqual(len(response.context["items"]), 25)
        response = self.client.get(reverse("estudio_lista"), {"agrupar": "paciente", "carpeta_id": self.paciente.pk, "page": 2})
        self.assertEqual(len(response.context["items"]), 5)
        self.assertContains(response, "agrupar=paciente")
        self.assertContains(response, f"carpeta_id={self.paciente.pk}")

    def test_arbol_admin_solo_materializa_archivos_de_la_pagina(self):
        estudio = self.estudio()
        self.archivos(estudio, 205)
        response = self.client.get(reverse("estudio_detalle", args=[estudio.pk]))
        self.assertEqual(response.context["total_archivos"], 205)
        self.assertEqual(response.context["tree"]["total_archivos_recursivo"], 100)
        self.assertNotContains(response, 'title="0100.dcm"')
        ultima = self.client.get(reverse("estudio_detalle", args=[estudio.pk]), {"archivos_pagina": 3})
        self.assertEqual(ultima.context["tree"]["total_archivos_recursivo"], 5)
        self.assertNotContains(ultima, 'title="0000.dcm"')

    def test_agrupacion_respeta_filtro_de_estado(self):
        self.estudio(estado=EstadoEstudio.BORRADOR)
        response = self.client.get(reverse("estudio_lista"), {"agrupar": "paciente", "estado": EstadoEstudio.PUBLICADO})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_paciente_ve_pagina_acotada_y_no_historicos(self):
        estudio = self.estudio(estado=EstadoEstudio.PUBLICADO)
        self.archivos(estudio, 105)
        Archivo.objects.filter(estudio=estudio, nombre_archivo="0000.dcm").update(estado=EstadoArchivo.REEMPLAZADO)
        cuenta = Usuario.objects.create_user(username="paciente_paginas", email="paciente@example.test", password="clave-test", rol=RolUsuario.PACIENTE, estado=EstadoCuenta.HABILITADA)
        self.paciente.usuario = cuenta
        self.paciente.save(update_fields=["usuario"])
        self.client.force_login(cuenta)
        response = self.client.get(reverse("estudio_ver", args=[estudio.pk]))
        self.assertEqual(response.context["total_archivos"], 104)
        self.assertEqual(response.context["tree"]["total_archivos_recursivo"], 100)
        self.assertNotContains(response, 'title="0000.dcm"')

    def test_tablero_derivante_precarga_solo_cuatro_archivos(self):
        cuenta = Usuario.objects.create_user(username="doc_paginas", email="doc@example.test", password="clave-test", rol=RolUsuario.ODONTOLOGO, estado=EstadoCuenta.HABILITADA)
        profesional = Odontologo.objects.create(usuario=cuenta, nombre="Luis", apellido="Prueba", matricula="MP-1")
        estudio = self.estudio(estado=EstadoEstudio.PUBLICADO)
        Autorizacion.objects.create(estudio=estudio, odontologo=profesional)
        self.archivos(estudio, 205)
        self.client.force_login(cuenta)
        response = self.client.get(reverse("dashboard_odontologo"))
        item = list(response.context["estudios"])[0]
        self.assertEqual(item.cantidad_archivos, 205)
        self.assertEqual(len(item.archivos_resumen), 4)
        self.assertNotIn("archivos", getattr(item, "_prefetched_objects_cache", {}))
