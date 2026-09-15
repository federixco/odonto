import re

with open('templates/core/includes/icon.html', 'r', encoding='utf-8') as f:
    text = f.read()

new_icons = '''{% elif name == "grid" %}<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
{% elif name == "file" %}<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>'''

text = text.replace('{% endif %}', new_icons + '\n{% endif %}')

with open('templates/core/includes/icon.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Added icons")
