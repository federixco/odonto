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
            datos = importacion.datos_detectados or {}
            self.initial.update(
                {
                    "paciente": importacion.paciente_sugerido_id,
                    "tipo": datos.get("formato", ""),
                    "fecha_estudio": datos.get("fecha_estudio", ""),
                    "observaciones": datos.get("descripcion", ""),
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
            datos = importacion.datos_detectados or {}
            partes = datos.get("nombre_paciente", "").strip().split()
            # DICOM suele expresar el nombre como APELLIDO^NOMBRE. Si el origen
            # no respeta esa convención, el administrador puede corregirlo.
            apellido = partes[0] if len(partes) > 1 else ""
            nombre = " ".join(partes[1:]) if len(partes) > 1 else (partes[0] if partes else "")
            self.initial.update(
                {
                    "nombre": nombre,
                    "apellido": apellido,
                    "dni": datos.get("identificador_paciente", ""),
                    "fecha_nacimiento": datos.get("fecha_nacimiento", ""),
                }
            )
        self.fields["dni"].help_text = "Dato sugerido por el archivo. Verificá que sea el DNI real antes de guardar."
