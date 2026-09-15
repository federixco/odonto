import re

with open('apps/estudios/templates/estudios/derivante_selector.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Add a skip option
skip_option = '''
        <label class="derivante-option{% if not seleccionado %} is-selected{% endif %}" data-derivante-card data-search="" data-status="">
            <input type="radio" name="derivante" value="" {% if not seleccionado %}checked{% endif %}>
            <span class="professional-avatar" aria-hidden="true" style="background:#e0e6ed;color:#5a6b7c">?</span>
            <span class="derivante-identity">
                <strong>Asignar m\u00e1s tarde</strong>
                <small>El estudio quedar\u00e1 como borrador y sin permisos.</small>
            </span>
            <span class="derivante-check" aria-hidden="true">\u2713</span>
        </label>
'''

# Insert it before the loop
text = text.replace('{% for odontologo in form.fields.derivante.queryset %}', skip_option + '{% for odontologo in form.fields.derivante.queryset %}')

# Remove 'required' from the radio buttons inside the loop
text = text.replace('{% if seleccionado == odontologo.pk|stringformat:\'s\' %}checked{% endif %} required>', '{% if seleccionado == odontologo.pk|stringformat:\'s\' %}checked{% endif %}>')

with open('apps/estudios/templates/estudios/derivante_selector.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Modified derivante_selector.html")
