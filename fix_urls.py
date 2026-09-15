import re

with open('apps/estudios/urls.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the views import
text = text.replace('PublicarEstudioView)', 'PublicarEstudioView, VerEstudioView)')

# Insert the URL pattern
pattern = 'path("importar/", CrearImportacionView.as_view(), name="importacion_crear"),'
new_pattern = 'path("<int:pk>/ver/", VerEstudioView.as_view(), name="estudio_ver"),\n    ' + pattern
text = text.replace(pattern, new_pattern)

with open('apps/estudios/urls.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Fixed urls.py")
