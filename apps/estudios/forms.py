from django import forms
from apps.pacientes.models import Paciente
from .models import Estudio

class EstudioForm(forms.ModelForm):
    class Meta:
        model = Estudio
        fields = ["paciente", "tipo", "fecha_estudio", "observaciones"]
        widgets = {
            "fecha_estudio": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }


class ConfirmarImportacionForm(EstudioForm):
    """Formulario final: transforma una detección revisada en un estudio."""

    def __init__(self, *args, importacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        if importacion and not self.is_bound:
            self.initial.update(
                {
                    "paciente": importacion.paciente_sugerido_id,
                    "tipo": importacion.get_formato_detectado_display(),
                    "fecha_estudio": importacion.fecha_estudio_detectada,
                    "observaciones": importacion.descripcion_detectada,
                }
            )


class RegistrarPacienteDetectadoForm(forms.ModelForm):
    """Ficha clínica creada desde datos sugeridos por una importación.

    No crea una cuenta web del paciente: esa opción sigue siendo excepcional y
    se gestiona posteriormente desde su ficha clínica.
    """

    class Meta:
        model = Paciente
        fields = ["nombre", "apellido", "dni", "fecha_nacimiento", "obra_social"]
        widgets = {"fecha_nacimiento": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, importacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        if importacion and not self.is_bound:
            partes = importacion.nombre_paciente_detectado.strip().split()
            # DICOM suele expresar el nombre como APELLIDO^NOMBRE. Si el origen
            # no respeta esa convención, el administrador puede corregirlo.
            apellido = partes[0] if len(partes) > 1 else ""
            nombre = " ".join(partes[1:]) if len(partes) > 1 else (partes[0] if partes else "")
            self.initial.update(
                {
                    "nombre": nombre,
                    "apellido": apellido,
                    "dni": importacion.identificador_paciente_detectado,
                    "fecha_nacimiento": importacion.fecha_nacimiento_detectada,
                }
            )
        self.fields["dni"].help_text = "Dato sugerido por el archivo. Verificá que sea el DNI real antes de guardar."
