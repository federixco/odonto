import re

with open('apps/estudios/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_logic = '''        estudios_recientes = (
            Estudio.objects.select_related("paciente")
            .exclude(estado=EstadoEstudio.ELIMINADO)
            .order_by("-created_at")[:5]
        )
        return render(
            request,
            "estudios/importacion_crear.html",
            {"estudios_recientes": estudios_recientes},
        )'''

new_logic = '''        estudios_recientes = (
            Estudio.objects.select_related("paciente")
            .exclude(estado=EstadoEstudio.ELIMINADO)
            .order_by("-created_at")[:5]
        )
        pendientes = ImportacionEstudio.objects.filter(
            iniciada_por=request.user, 
            estado=EstadoImportacion.PENDIENTE_CONFIRMACION
        ).order_by("-created_at")
        
        return render(
            request,
            "estudios/importacion_crear.html",
            {
                "estudios_recientes": estudios_recientes,
                "pendientes": pendientes,
            },
        )'''

text = text.replace(old_logic, new_logic)

with open('apps/estudios/views.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated CrearImportacionView with pendientes")
