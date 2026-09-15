with open('apps/estudios/templates/estudios/estudio_detalle.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = lines[:28] + [
    '            {% if tree %}\n',
    '            <div class="folder-root">\n',
    '                {% include "estudios/_folder_node.html" with node=tree %}\n',
    '            </div>\n',
    '            {% else %}\n',
    '            <div class="directory-empty compact-empty"><h3>Todavía no hay archivos asociados</h3><p>Podés agregarlos manualmente desde la opción inferior.</p></div>\n',
    '            {% endif %}\n'
] + lines[38:]

with open('apps/estudios/templates/estudios/estudio_detalle.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
