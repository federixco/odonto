import re

with open('apps/estudios/templates/estudios/estudio_detalle.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(
    r'{% if archivos_pagina %}.*?{% endif %}\n            {% else %}\n            <div class="directory-empty compact-empty"><h3>Todav\?\?a no hay archivos asociados</h3><p>Pod\?\?s agregarlos manualmente desde la opci\?\?n inferior.</p></div>\n            {% endif %}',
    '''{% if tree %}
            <div class="folder-root">
                {% include 'estudios/_folder_node.html' with node=tree %}
            </div>
            {% else %}
            <div class="directory-empty compact-empty"><h3>Todavía no hay archivos asociados</h3><p>Podés agregarlos manualmente desde la opción inferior.</p></div>
            {% endif %}''',
    text,
    flags=re.DOTALL
)

with open('apps/estudios/templates/estudios/estudio_detalle.html', 'w', encoding='utf-8') as f:
    f.write(text)
