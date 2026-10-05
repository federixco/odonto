import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accesos.models import Autorizacion
from apps.archivos.models import Archivo
from apps.auditoria.models import LogActividad
from apps.estudios.models import Estudio
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo
from apps.estudios.services.visor import preparar, solicitar, guardar, directorio, huella, procesar_visor_uno
from apps.estudios.services.visor_dicom import cabecera, agrupar
from tests.visor_fixtures import dicom, dicom_multiframe, dicom_rle


class VisorTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(VISOR_CACHE_DIR=Path(self.tmp.name))
        override.enable(); self.addCleanup(override.disable)
        User = get_user_model()
        def user(name, rol):
            return User.objects.create_user(username=name, email=name+'@example.test', rol=rol, estado='HABILITADA')
        self.admin = user('admin', 'ADMINISTRADOR')
        self.paciente_user = user('paciente', 'PACIENTE')
        self.odon_user = user('odontologo', 'ODONTOLOGO')
        self.ajeno = user('ajeno', 'ODONTOLOGO')
        self.paciente = Paciente.objects.create(nombre='Sintético', apellido='Prueba', dni='TEST-123', usuario=self.paciente_user)
        self.odon = Odontologo.objects.create(nombre='Prueba', apellido='Prueba', matricula='TEST-1', usuario=self.odon_user)
        self.estudio = Estudio.objects.create(paciente=self.paciente, tipo='Prueba', fecha_estudio=date.today(), estado='PUBLICADO', fecha_publicacion=timezone.now())
        self.autorizacion = Autorizacion.objects.create(odontologo=self.odon, estudio=self.estudio)
        self.archivo = self.file()

    def file(self, **kwargs):
        data = dict(estudio=self.estudio, nombre_archivo='test.stl', formato='STL', categoria='MODELO_3D',
                    ruta_almacenamiento='privado/test.stl', tamano=100, estado='COMPLETO')
        data.update(kwargs)
        return Archivo.objects.create(**data)

    def url(self, name, *args):
        return reverse('visor_'+name, args=[self.estudio.pk, *args])

    def test_visitante_no_metadata_ni_firma(self):
        for ruta in [self.url('catalogo'), self.url('estudio'), self.url('contenido', self.archivo.pk), self.url('serie', 'x')]:
            respuesta = self.client.get(ruta)
            self.assertEqual(respuesta.status_code, 401)
            self.assertIn('no-store', respuesta['Cache-Control'])

    @patch('apps.estudios.visor_views.generar_url_previsualizacion', return_value='https://storage.test/temporal')
    def test_roles_autorizados_pueden_ver_sin_cache(self, firmar):
        for user in [self.admin, self.paciente_user, self.odon_user]:
            self.client.force_login(user)
            response = self.client.get(self.url('contenido', self.archivo.pk))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response['Referrer-Policy'], 'no-referrer')
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(self.client.get(self.url('catalogo')).status_code, 200)
        self.assertEqual(firmar.call_count, 3)

    @patch('apps.estudios.visor_views.generar_url_previsualizacion')
    def test_revocado_ajeno_borrador_eliminado_y_deshabilitado(self, firmar):
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(self.url('catalogo')).status_code, 403)
        self.autorizacion.estado_acceso = 'REVOCADO'
        self.autorizacion.fecha_revocacion = timezone.now()
        self.autorizacion.revocado_por = self.admin
        self.autorizacion.save()
        self.client.force_login(self.odon_user)
        self.assertEqual(self.client.get(self.url('contenido', self.archivo.pk)).status_code, 403)
        for estado in ['BORRADOR', 'EN_REVISION', 'ELIMINADO']:
            self.estudio.estado = estado; self.estudio.save()
            self.client.force_login(self.paciente_user)
            self.assertEqual(self.client.get(self.url('catalogo')).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url('catalogo')).status_code, 403)
        self.admin.estado='DESHABILITADA'; self.admin.save()
        self.assertIn(self.client.get(self.url('catalogo')).status_code, [401, 403])
        firmar.assert_not_called()

    @patch('apps.estudios.visor_views.generar_url_previsualizacion')
    def test_archivo_ajeno_incompleto_y_solo_importacion_no_se_firma(self, firmar):
        self.client.force_login(self.admin)
        otro = Estudio.objects.create(paciente=self.paciente, tipo='Otro', fecha_estudio=date.today())
        for cambios in [dict(estudio=otro), dict(estudio=None), *[dict(estado=x) for x in ['CARGANDO','INCORRECTO','REEMPLAZADO','PURGADO']]]:
            a = self.file(**cambios)
            self.assertEqual(self.client.get(self.url('contenido', a.pk)).status_code, 404)
        firmar.assert_not_called()

    def test_admin_borrador_y_paciente_solo_suyo(self):
        self.estudio.estado='BORRADOR'; self.estudio.save()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url('estudio')).status_code, 200)
        otro = Paciente.objects.create(nombre='Otro', apellido='Prueba', dni='TEST-456')
        self.estudio.paciente=otro; self.estudio.estado='PUBLICADO'; self.estudio.save()
        self.client.force_login(self.paciente_user)
        self.assertEqual(self.client.get(self.url('catalogo')).status_code, 403)

    def test_catalogo_independiente_de_paginacion(self):
        for n in range(60): self.file(nombre_archivo=f'{n}.stl')
        self.client.force_login(self.admin)
        self.assertEqual(len(self.client.get(self.url('catalogo')).json()['modelos']), 61)

    def test_enlace_directo_selecciona_archivo_o_serie_del_estudio(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url('catalogo'), {'archivo':self.archivo.pk}).json()['seleccion'], f'm-{self.archivo.pk}')
        d = self.file(formato='DICOM', tamano=10000)
        with patch('apps.estudios.services.visor.leer_objeto', return_value=dicom()):
            guardar(directorio()/f'{self.estudio.pk}.json', preparar(self.estudio))
        data = self.client.get(self.url('catalogo'), {'archivo':d.pk}).json()
        self.assertEqual(data['seleccion'], f"s-{data['series'][0]['id']}")
        for requested in ['invalido', '9'*100, str(d.pk+1000)]:
            self.assertIsNone(self.client.get(self.url('catalogo'), {'archivo':requested}).json()['seleccion'])
        d.estado='REEMPLAZADO'; d.save()
        self.assertIsNone(self.client.get(self.url('catalogo'), {'archivo':d.pk}).json()['seleccion'])

    def test_auditoria_csrf_token_y_deduplicacion(self):
        self.client.force_login(self.admin)
        config = self.client.get(self.url('estudio')).context['visor_config']
        body = dict(token=config['token'], resultado='renderizado', modo='modelo')
        for _ in range(3):
            self.assertEqual(self.client.post(self.url('eventos'), body, content_type='application/json').status_code, 200)
        self.assertEqual(LogActividad.objects.filter(resultado='Cliente reporta renderizado').count(), 1)
        csrf_client = Client(enforce_csrf_checks=True); csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(self.url('eventos'), body, content_type='application/json').status_code, 403)
        for invalid in [{}, [], dict(body, resultado='texto arbitrario'), dict(body, codigo='https://secret'), dict(body, token='invalido')]:
            self.assertEqual(self.client.post(self.url('eventos'), invalid, content_type='application/json').status_code, 400)
        self.client.force_login(self.odon_user)
        self.assertEqual(self.client.post(self.url('eventos'), body, content_type='application/json').status_code, 400)

    def test_indice_cache_renovacion_y_error_no_filtra_clave(self):
        a = self.file(formato='DICOM', categoria='DICOM', tamano=10000)
        self.client.force_login(self.admin)
        with patch('apps.estudios.services.visor.leer_objeto', return_value=dicom()) as leer:
            self.assertEqual(self.client.get(self.url('catalogo')).status_code, 202)
            self.assertTrue(procesar_visor_uno())
            self.assertEqual(leer.call_args.args[1], 10000)
        data = self.client.get(self.url('catalogo')).json()
        self.assertEqual(len(data['series']), 1)
        self.assertNotIn('privado/', json.dumps(data))
        self.assertEqual(self.client.get(data['series'][0]['url']).status_code, 200)
        a.estado='REEMPLAZADO'; a.save()
        self.assertEqual(self.client.get(self.url('contenido', a.pk)).status_code, 404)
        a.estado='COMPLETO'; a.save()
        solicitar(self.estudio)
        with patch('apps.estudios.services.visor.leer_objeto', side_effect=RuntimeError('credencial privada')):
            procesar_visor_uno()
        self.assertNotIn('credencial', (directorio()/f'{self.estudio.pk}.json').read_text())
        self.assertEqual(solicitar(self.estudio)['estado'], 'error')
        self.assertEqual(solicitar(self.estudio, reintentar=True)['estado'], 'preparando')
        self.assertEqual(solicitar(self.estudio)['estado'], 'preparando')
        with patch('apps.estudios.services.visor.leer_objeto', return_value=dicom()):
            self.assertTrue(procesar_visor_uno())
        self.assertEqual(solicitar(self.estudio)['estado'], 'listo')

    @patch('apps.estudios.visor_views.generar_url_previsualizacion')
    @override_settings(VISOR_MAX_MESH_BYTES=50)
    def test_modelo_excesivo_y_error_de_storage_no_filtran_url(self, firmar):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url('contenido', self.archivo.pk)).status_code, 413)
        firmar.assert_not_called()
        self.archivo.tamano = 30; self.archivo.save()
        firmar.side_effect = RuntimeError('https://privado.test/?credencial=secreto')
        response = self.client.get(self.url('contenido', self.archivo.pk))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'credencial', response.content)

    def test_limites_nuevos_invalidan_indice(self):
        antes = huella(self.estudio)
        with override_settings(VISOR_HEADER_BYTES=123456):
            self.assertNotEqual(antes, huella(self.estudio))


class DicomMetadataTests(SimpleTestCase):
    def parsed(self, z=0, **kwargs):
        content = dicom(z, **kwargs)
        return cabecera(content, z+1, len(content))[0]

    def test_series_espaciales_no_orden_nombre(self):
        serie = agrupar([self.parsed(z) for z in [2, 0, 1]])[0]
        self.assertTrue(serie['volumen'])
        self.assertEqual([a['archivo'] for a in serie['archivos']], [1,2,3])

    def test_geometrias_no_inventadas(self):
        scenarios = [dict(ImagePositionPatient=None), dict(ImageOrientationPatient=[1,0,0,1,0,0]),
                     dict(PixelSpacing=None), dict(FrameOfReferenceUID=None), dict(NumberOfFrames=2)]
        for campos in scenarios:
            with self.subTest(campos=campos):
                self.assertFalse(agrupar([self.parsed(z, **campos) for z in range(3)])[0]['volumen'])
        self.assertFalse(agrupar([self.parsed(z) for z in [0,1,5]])[0]['volumen'])
        self.assertFalse(agrupar([self.parsed(0),self.parsed(1),self.parsed(1)])[0]['volumen'])

    def test_no_mezcla_estudios_series_marcos(self):
        self.assertEqual(len(agrupar([self.parsed(), self.parsed(1, SeriesInstanceUID='1.2.3'), self.parsed(2, FrameOfReferenceUID='1.2.4')])), 3)

    def test_no_dicomdir_ni_corrupto_ni_uid_faltante(self):
        for data in [b'x'*1000, dicom(Rows=None, Columns=None), dicom(SeriesInstanceUID=None)]:
            metadata, reason = cabecera(data, 1, len(data))
            self.assertIsNone(metadata); self.assertTrue(reason)

    @override_settings(VISOR_MAX_VOLUME_BYTES=1000)
    def test_limite_memoria_no_impide_cortes(self):
        serie = agrupar([self.parsed(z) for z in range(3)])[0]
        self.assertFalse(serie['volumen'])
        self.assertEqual(serie['frames'], 3)

    def test_rle_y_multiframe_tienen_capacidades_distintas(self):
        contenido = dicom_multiframe()
        metadata, reason = cabecera(contenido, 1, len(contenido))
        self.assertIsNone(reason)
        self.assertEqual(metadata['frames'], 3)
        self.assertFalse(agrupar([metadata])[0]['volumen'])
        cabeceras = []
        for z in range(3):
            contenido = dicom_rle(z)
            metadata, reason = cabecera(contenido, z+1, len(contenido))
            self.assertIsNone(reason)
            cabeceras.append(metadata)
        self.assertTrue(agrupar(cabeceras)[0]['volumen'])
