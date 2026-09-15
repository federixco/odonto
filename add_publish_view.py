import re

with open('apps/estudios/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

view_code = '''
class PublicarEstudioView(AdminRequeridoMixin, View):
    """Permite al administrador publicar un estudio manualmente si tiene archivos completos."""
    def post(self, request, pk):
        estudio = get_object_or_404(Estudio.objects.exclude(estado=EstadoEstudio.ELIMINADO), pk=pk)
        try:
            estudio.publicar()
            messages.success(request, "El estudio fue publicado exitosamente.")
            LogActividad.objects.create(
                usuario=request.user,
                estudio=estudio,
                tipo_evento=TipoEvento.PUBLICACION,
                resultado="Estudio publicado manualmente",
                detalles=f"El estudio {estudio.pk} cambi a estado PUBLICADO."
            )
        except ValidationError as e:
            messages.error(request, e.message)
        return redirect("estudio_detalle", pk=estudio.pk)
'''

text = text.replace('class AgregarAccesoEstudioView', view_code + '\n\nclass AgregarAccesoEstudioView')

with open('apps/estudios/views.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Added PublicarEstudioView.")
