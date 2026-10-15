import uuid
from django import forms
from django.utils import timezone
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo
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

    estudios_revisados = forms.BooleanField(
        required=False,
        label="Revisé los estudios distintos y corresponde agruparlos en esta ficha con la fecha indicada.",
    )

    derivante = forms.ModelChoiceField(
        label="Odontólogo derivante",
        queryset=Odontologo.objects.none(),
        empty_label="No asignar todavía (Guardar como borrador)",
        required=False,
        help_text="Profesional que solicitó el estudio y podrá consultarlo.",
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, importacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estudios_revisados"].required = bool(importacion and importacion.requiere_revision_estudios)
        self.fields["derivante"].queryset = (
            Odontologo.objects.select_related("usuario")
            .filter(usuario__estado="HABILITADA")
            .order_by("apellido", "nombre", "matricula")
        )
        if importacion and not self.is_bound:
            datos = importacion.datos_detectados or {}
            self.initial.update(
                {
                    "paciente": importacion.paciente_sugerido_id,
                    "tipo": datos.get("formato", ""),
                    "fecha_estudio": datos.get("fecha_estudio") or timezone.now().date().isoformat(),
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
        self.fields["dni"].required = False
        self.fields["apellido"].required = False
        self.fields["nombre"].required = False
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
        dni_sugerido = self.initial.get("dni", "")
        if dni_sugerido:
            self.fields["dni"].help_text = "Dato sugerido por el archivo. Verificá que sea el DNI real antes de guardar."
        else:
            self.fields["dni"].help_text = "Opcional. Si lo dejás en blanco, se generará un identificador provisional automático (TEMP-)."

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        return nombre or "Paciente"

    def clean_dni(self):
        dni = (self.cleaned_data.get("dni") or "").strip()
        if not dni:
            return f"TEMP-{uuid.uuid4().hex[:8].upper()}"
        return dni

    def clean_apellido(self):
        apellido = (self.cleaned_data.get("apellido") or "").strip()
        return apellido or "Sin clasificar"


