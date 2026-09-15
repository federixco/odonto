with open('apps/estudios/urls.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('RevocarAccesoEstudioView)', 'RevocarAccesoEstudioView, PublicarEstudioView)')
text = text.replace('path("<int:pk>/accesos/agregar/",', 'path("<int:pk>/publicar/", PublicarEstudioView.as_view(), name="estudio_publicar"),\n    path("<int:pk>/accesos/agregar/",')

with open('apps/estudios/urls.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('URL added')
