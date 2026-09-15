with open('apps/estudios/templates/estudios/estudio_detalle.html', 'r', encoding='utf-8') as f:
    text = f.read()

replacement = """<span class="account-status study-state {% if estudio.estado == 'PUBLICADO' %}status-enabled{% elif estudio.estado == 'BORRADOR' %}status-pending{% elif estudio.estado == 'ELIMINADO' %}status-disabled{% endif %}"><span></span>{{ estudio.get_estado_display }}</span>
        {% if estudio.estado == 'BORRADOR' or estudio.estado == 'EN_REVISION' %}
        <form method="post" action="{% url 'estudio_publicar' estudio.pk %}" style="display: inline-block; margin-left: 12px;">
            {% csrf_token %}
            <button type="submit" class="button button-small">Publicar Estudio</button>
        </form>
        {% endif %}"""

text = text.replace("""<span class="account-status study-state {% if estudio.estado == 'PUBLICADO' %}status-enabled{% elif estudio.estado == 'BORRADOR' %}status-pending{% elif estudio.estado == 'ELIMINADO' %}status-disabled{% endif %}"><span></span>{{ estudio.get_estado_display }}</span>""", replacement)

with open('apps/estudios/templates/estudios/estudio_detalle.html', 'w', encoding='utf-8') as f:
    f.write(text)
