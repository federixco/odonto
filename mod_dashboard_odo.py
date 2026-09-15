import re

with open('apps/usuarios/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_logic = '''class DashboardOdontologoView(OdontologoRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_odontologo.html"'''

new_logic = '''class DashboardOdontologoView(OdontologoRequeridoMixin, TemplateView):
    template_name = "usuarios/dashboard_odontologo.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            odontologo = self.request.user.odontologo
        except Exception:
            raise PermissionDenied("La cuenta no está vinculada a un odontólogo.")
        
        context["odontologo"] = odontologo
        
        # Obtener autorizaciones vigentes y estudios publicados
        from apps.core.enums import EstadoAcceso, EstadoEstudio
        from apps.estudios.models import Estudio
        
        estudios = Estudio.objects.filter(
            autorizaciones__odontologo=odontologo,
            autorizaciones__estado_acceso=EstadoAcceso.VIGENTE,
            estado=EstadoEstudio.PUBLICADO
        ).select_related('paciente').order_by('-fecha_estudio', '-created_at')
        
        context["estudios"] = estudios
        return context'''

text = text.replace(old_logic, new_logic)

with open('apps/usuarios/views.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated DashboardOdontologoView")
