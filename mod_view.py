import re

with open('apps/estudios/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_logic = '''            derivante = form.cleaned_data["derivante"]
            Autorizacion.objects.create(
                estudio=estudio,
                odontologo=derivante,
            )
            try:
                estudio.publicar()
            except ValidationError:
                pass'''

new_logic = '''            derivante = form.cleaned_data.get("derivante")
            if derivante:
                Autorizacion.objects.create(
                    estudio=estudio,
                    odontologo=derivante,
                )
                try:
                    estudio.publicar()
                except ValidationError:
                    pass'''

text = text.replace(old_logic, new_logic)

with open('apps/estudios/views.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Modified ConfirmarImportacionView")
