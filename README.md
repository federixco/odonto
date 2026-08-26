# SISETMA

Sistema web para la gestión, publicación y consulta de estudios odontológicos de D.O.C.

Este repositorio está organizado como un monolito modular de Django. Cada módulo representa una responsabilidad del dominio y deberá comunicarse con los demás mediante servicios explícitos, evitando dependencias circulares.

La estructura inicial se encuentra explicada en `docs/arquitectura/estructura-carpetas.md`.

## Arranque local

Con Python instalado, ejecutar desde la raíz del proyecto:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

El entorno de desarrollo usa SQLite por defecto. Las credenciales y valores
específicos de cada entorno deben definirse en un archivo `.env` local, que no
se versiona.
