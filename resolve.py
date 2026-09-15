with open('apps/estudios/templates/estudios/estudio_detalle.html', 'r', encoding='utf-8') as f:
    text = f.read()

start_marker = '{% if archivos_pagina %}'
end_marker = '{% endif %}'

start_idx = text.find(start_marker)

# Fede's code has 3 endifs inside the file block:
# 1. {% if archivo.hash_sha256 %}...{% endif %}
# 2. {% if archivos_pagina.paginator.num_pages > 1 %}...{% endif %}
# 3. {% endif %} closing the big {% if archivos_pagina %}...{% else %}...{% endif %}
# So we want to replace from `start_idx` to the 3rd `{% endif %}`.

idx = start_idx
for _ in range(3):
    idx = text.find(end_marker, idx) + len(end_marker)

end_idx = idx

tree_code = '''{% if tree %}
            <div class="folder-root">
                {% include 'estudios/_folder_node.html' with node=tree %}
            </div>
            {% else %}
            <div class="directory-empty compact-empty"><h3>Todavía no hay archivos asociados</h3><p>Podés agregarlos manualmente desde la opción inferior.</p></div>
            {% endif %}'''

if start_idx != -1 and end_idx != -1:
    new_text = text[:start_idx] + tree_code + text[end_idx:]
    with open('apps/estudios/templates/estudios/estudio_detalle.html', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Replaced")
else:
    print("Not found")
