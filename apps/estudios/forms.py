from django import forms
from .models import Estudio

class EstudioForm(forms.ModelForm):
    class Meta:
        model = Estudio
        fields = ["paciente", "tipo", "fecha_estudio", "observaciones"]
        widgets = {
            "fecha_estudio": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }
