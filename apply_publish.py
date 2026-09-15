import re

with open('apps/estudios/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

# For AgregarAccesoEstudioView
text = text.replace(
    '''            if creada or reactivada:
                LogActividad.objects.create(''',
    '''            if creada or reactivada:
                try:
                    estudio.publicar()
                except ValidationError:
                    pass
                LogActividad.objects.create('''
)

# For ConfirmarImportacionView
text = text.replace(
    '''            Autorizacion.objects.create(
                estudio=estudio,
                odontologo=derivante,
            )
            LogActividad.objects.create(usuario=request.user, estudio=estudio, tipo_evento=TipoEvento.IMPORTACION_CONFIRMADA''',
    '''            Autorizacion.objects.create(
                estudio=estudio,
                odontologo=derivante,
            )
            try:
                estudio.publicar()
            except ValidationError:
                pass
            LogActividad.objects.create(usuario=request.user, estudio=estudio, tipo_evento=TipoEvento.IMPORTACION_CONFIRMADA'''
)

with open('apps/estudios/views.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Modifications applied.")
