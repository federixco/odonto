"""Servidor de pruebas SOLO loopback y datos sintéticos; no inicia BD ni S3 reales.

Sirve el template y el build reales. El segundo puerto simula una redirección
prefirmada cross-origin y verifica que no reciba cookies del portal.
"""
import json
import mimetypes
import os
import re
import secrets
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.test'
import django
django.setup()
from django.template.loader import render_to_string
from apps.estudios.visor_views import limites
from tests.visor_fixtures import STL, PLY, dicom, dicom_multiframe, dicom_rle

ROOT = Path(__file__).resolve().parents[1]
FILES = {1: STL, 2: PLY, 200: dicom_multiframe(),
         **{100+z: dicom(z) for z in range(16)}, **{300+z: dicom_rle(z) for z in range(3)}}
SERIES = {
    'sintetica': {'archivos': list(range(100,116)), 'frames': 16, 'volumen': True},
    'multiframe': {'archivos': [200], 'frames': 3, 'volumen': False},
    'rle': {'archivos': [300,301,302], 'frames': 3, 'volumen': True},
}
READS = []
EVENTS = []
PREFIX = '/estudios/1/visor/'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, content, mime='application/json', code=200, **headers):
        if not isinstance(content, bytes): content = json.dumps(content).encode()
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        for k,v in headers.items(): self.send_header(k.replace('_','-'), v)
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = urlparse(self.path).path
        if self.server.server_port == 8766:
            if path.startswith('/objeto/') and path.split('/')[-1].isdigit():
                pk = int(path.split('/')[-1])
                READS.append({'id': pk, 'cookie': self.headers.get('Cookie', ''), 'origin': self.headers.get('Origin', '')})
                return self.send(FILES[pk], 'application/octet-stream', Access_Control_Allow_Origin='http://127.0.0.1:8765')
            return self.send({}, code=404)
        if path == '/':
            config = {'catalogo': PREFIX+'catalogo/', 'eventos': PREFIX+'eventos/', 'token':'sintetico', 'limites':limites()}
            html = render_to_string('estudios/visor.html', {
                'estudio':SimpleNamespace(pk=1, tipo='Estudio sintético · Prueba del visor', fecha_estudio=date(2026,10,4)),
                'visor_config': config, 'volver':'/', 'request':SimpleNamespace(user=SimpleNamespace(rol='ADMINISTRADOR')),
                'csrf_token':'a'*32,
            })
            return self.send(html.encode(), 'text/html', Set_Cookie='sesion_prueba=solo_portal; Path=/')
        if path == '/diagnostico':
            return self.send({'lecturas':READS, 'eventos':EVENTS})
        if path == PREFIX+'catalogo/':
            requested = parse_qs(urlparse(self.path).query).get('archivo', [''])[0]
            selection = next((f's-{key}' for key,s in SERIES.items() if requested in map(str,s['archivos'])), None)
            if requested in ['1','2']: selection=f'm-{requested}'
            return self.send({'estado':'listo','omitidos':[], 'seleccion':selection, 'modelos':[
                {'id':pk, 'nombre':f'modelo.{fmt.lower()}', 'formato':fmt, 'bytes':len(FILES[pk]), 'disponible':True,
                 'url':PREFIX+f'archivos/{pk}/contenido/'} for pk,fmt in [(1,'STL'),(2,'PLY')]],
                'series':[{'id':key,'nombre':f'Serie {key}','frames':s['frames'],'volumen':s['volumen'],
                           'motivo':'','url':PREFIX+f'series/{key}/'} for key,s in SERIES.items()]})
        series_match = re.fullmatch(PREFIX+r'series/(\w+)/', path)
        if series_match and series_match[1] in SERIES:
            key = series_match[1]; s = SERIES[key]
            return self.send({'id':key,'frames':s['frames'],'volumen':s['volumen'],'motivo':'','memoria_estimada':2*1024*1024,
                              'archivos':[{'id':pk, 'frames':3 if pk==200 else 1, 'bytes':len(FILES[pk]),
                                           'url':PREFIX+f'archivos/{pk}/contenido/'} for pk in s['archivos']]})
        match = re.fullmatch(PREFIX+r'archivos/(\d+)/contenido/', path)
        if match:
            return self.send(b'', code=302, Location='http://127.0.0.1:8766/objeto/'+match[1])
        if path.startswith('/static/'):
            target = (ROOT / path.lstrip('/')).resolve()
            if target.is_relative_to(ROOT/'static') and target.is_file():
                return self.send(target.read_bytes(), mimetypes.guess_type(target)[0] or 'application/octet-stream')
        return self.send({}, code=404)

    def do_POST(self):
        if urlparse(self.path).path == '/__test_shutdown':
            token = os.environ.get('VISOR_FIXTURE_TOKEN', '')
            if self.server.server_port != 8765 or not token or not secrets.compare_digest(token, self.headers.get('X-Test-Token', '')):
                return self.send({}, code=403)
            self.send({'cerrando':True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if urlparse(self.path).path == PREFIX+'eventos/':
            EVENTS.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            return self.send({'registrado':True})
        return self.do_GET()


if __name__ == '__main__':
    other = ThreadingHTTPServer(('127.0.0.1',8766), Handler)
    threading.Thread(target=other.serve_forever,daemon=True).start()
    print('Visor sintético: http://127.0.0.1:8765/', flush=True)
    with ThreadingHTTPServer(('127.0.0.1',8765), Handler) as portal:
        try:
            portal.serve_forever()
        finally:
            other.shutdown()
            other.server_close()
