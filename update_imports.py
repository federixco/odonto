import re

with open('apps/estudios/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'from apps.core.mixins import AdminRequeridoMixin',
    'from apps.core.mixins import AdminRequeridoMixin, EstudioAccesoMixin'
)

with open('apps/estudios/views.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Added EstudioAccesoMixin to imports")
