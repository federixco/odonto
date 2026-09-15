import re

with open('apps/estudios/templates/estudios/importacion_crear.html', 'r', encoding='utf-8') as f:
    text = f.read()

banner_html = '''
    {% if pendientes %}
    <section class="admin-card recent-studies" style="border: 2px solid #ffab00; background: #fffcf5; margin-bottom: 2rem;">
        <div class="recent-studies-heading">
            <div>
                <p class="eyebrow" style="color: #b27b00;">ATENCI\u00d3N REQUERIDA</p>
                <h2>Importaciones sin confirmar</h2>
                <p>Ten\u00e9s carpetas que se subieron pero todav\u00eda no se confirmaron como estudios.</p>
            </div>
        </div>
        <ul class="recent-study-list">
            {% for pendiente in pendientes %}
            <li>
                <a href="{% url 'importacion_detalle' pendiente.pk %}">
                    <span class="professional-avatar" aria-hidden="true" style="background:#ffab00; color:#fff">!</span>
                    <span class="recent-study-patient">
                        <strong>{{ pendiente.nombre_carpeta }}</strong>
                        <small>{{ pendiente.cantidad_archivos }} archivos subidos &middot; {{ pendiente.created_at|date:'d/m/Y H:i' }}</small>
                    </span>
                    <span class="account-status status-pending"><span></span>Pendiente</span>
                    <span class="recent-study-arrow" aria-hidden="true">\u2192</span>
                </a>
            </li>
            {% endfor %}
        </ul>
    </section>
    {% endif %}
'''

text = text.replace(
    '<section class="admin-card quick-upload-card" aria-labelledby="upload-title">',
    banner_html + '\n    <section class="admin-card quick-upload-card" aria-labelledby="upload-title">'
)

with open('apps/estudios/templates/estudios/importacion_crear.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated importacion_crear.html")
