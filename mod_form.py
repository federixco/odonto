import re

with open('apps/estudios/forms.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
'''    derivante = forms.ModelChoiceField(
        label="Odontólogo derivante",
        queryset=Odontologo.objects.none(),
        empty_label=None,
        help_text="Profesional que solicitó el estudio y podrá consultarlo.",
        widget=forms.RadioSelect,
    )''',
'''    derivante = forms.ModelChoiceField(
        label="Odontólogo derivante",
        queryset=Odontologo.objects.none(),
        empty_label="No asignar todavía (Guardar como borrador)",
        required=False,
        help_text="Profesional que solicitó el estudio y podrá consultarlo.",
        widget=forms.RadioSelect,
    )'''
)

with open('apps/estudios/forms.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Modified ConfirmarImportacionForm")
