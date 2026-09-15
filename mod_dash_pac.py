import re

with open('apps/usuarios/templates/usuarios/dashboard_paciente.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '<span class="patient-study-status">Publicado</span>',
    '''<div style="margin-top: 1rem;">
                    <a href="{% url 'estudio_ver' estudio.pk %}" class="button button-small" style="width: 100%; text-align: center;">Ver archivos &rarr;</a>
                </div>'''
)

with open('apps/usuarios/templates/usuarios/dashboard_paciente.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated dashboard_paciente.html")
