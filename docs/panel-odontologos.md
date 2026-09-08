# Panel de odontólogos del administrador

## Alcance

La gestión de odontólogos reutiliza la identidad visual
de D.O.C.: azul petróleo, turquesa, tarjetas claras, botones y campos consistentes.
El administrador entra directamente al listado de odontólogos, sin una pantalla
de Inicio intermedia. La URL anterior se conserva como redirección protegida.
No se cambiaron modelos, migraciones, reglas de habilitación ni permisos.
Tampoco se modificaron los paneles del odontólogo y del paciente.

Pantallas incluidas:

- `/admin-centro/`: dirección anterior, redirige a `/odontologos/`.
- `/odontologos/`: entrada principal del administrador, listado, búsqueda, estados y resultados vacíos.
- `/odontologos/crear/`: alta de profesional con cuenta habilitada.
- `/odontologos/<id>/`: ficha y acciones de acceso.
- `/odontologos/<id>/editar/`: edición del perfil, sin cambiar credenciales o estado.

## Organización del código

| Archivo | Responsabilidad |
| --- | --- |
| `templates/core/admin_base.html` | Marca, navegación, cierre de sesión POST, mensajes y pie del panel. |
| `static/core/css/public.css` | Paleta, tipografía, botones, campos y ayudas compartidos. |
| `static/core/css/admin.css` | Disposición del panel, directorio, estados y adaptación móvil. |
| `apps/usuarios/views.py` | Entrada por rol al listado y compatibilidad de la dirección anterior. |
| `apps/usuarios/templates/usuarios/odontologo_*.html` | Listado, ficha, alta y edición; el autorregistro conserva su base pública. |
| `apps/usuarios/templates/usuarios/includes/estado_cuenta.html` | Etiqueta de estado con texto y color. |
| `apps/usuarios/templates/usuarios/includes/odontologo_form.html` | Campos compartidos de alta y edición. |
| `templates/core/includes/form_field.html` | Campos originales de Django, con errores, etiquetas y ayuda. |
| `apps/usuarios/forms.py` | Autocompletado y ayuda de contraseña; validación y guardado existentes. |
| `apps/usuarios/tests/test_panel_presentacion.py` | Pruebas de presentación y conservación de las reglas de acceso. |

## Comportamiento conservado

- La búsqueda es GET y mantiene el parámetro `q` existente. El contador muestra
  la cantidad real de resultados de esa búsqueda, no el total global.
- El alta desde el centro crea una cuenta habilitada; el autorregistro público
  sigue creando una cuenta pendiente.
- Habilitar, deshabilitar y cerrar sesión siguen siendo operaciones POST con
  CSRF. Deshabilitar muestra primero una explicación desplegable; abrirla no
  cambia el estado. El cambio solo se envía al pulsar el botón de confirmación.
- La edición conserva el usuario, la contraseña y el estado de acceso.
- Los permisos siguen en las vistas del servidor: ocultar o mostrar controles
  en HTML no sustituye esas verificaciones.
- El listado se presenta como tabla en escritorio y como filas tipo ficha en
  celular. Conserva encabezados y roles de tabla para tecnologías de asistencia.
- La navegación, la búsqueda y los formularios funcionan sin JavaScript. El JS
  compartido solo agrega el botón para mostrar u ocultar contraseñas.

## Comprobación

```powershell
.\.venv\Scripts\python.exe -B manage.py test --settings=config.settings.test
.\.venv\Scripts\python.exe -B manage.py check --settings=config.settings.test
.\.venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run --settings=config.settings.test
```

La suite completa pasa con 72 pruebas, incluidas 12 del panel y 2 de entrada
directa del administrador. Cubren
presentación, búsquedas, datos escapados, formularios inválidos, edición válida,
cambios de estado, CSRF y rechazo de visitantes y otros roles. Las escrituras de
las pruebas ocurren en SQLite aislado, no en MySQL ni en la base de vista previa.

Revisión manual: iniciar sesión como administrador; recorrer listado, ficha,
alta y edición; buscar una matrícula existente y una inexistente; comprobar
los controles en escritorio y celular. Para probar guardado o cambios de estado
manualmente, utilizar una cuenta sintética, no modificar cuentas reales.

La vista previa continúa en `http://127.0.0.1:8001/`, con su SQLite temporal.
No se alteraron credenciales ni estados de las cuentas existentes para este
rediseño. El panel no crea nuevas funciones de estudios, almacenamiento o auditoría.
