# Landing pública de D.O.C.

## Alcance

La portada institucional está en `/` y no requiere iniciar sesión. Presenta los
servicios, el centro, el acceso a la plataforma, preguntas frecuentes y contacto.
El inicio de sesión conserva la URL `/auth/login/` y utiliza las vistas y el
formulario de autenticación de Django que ya tenía el proyecto.
El registro de odontólogos y todas las pantallas de recuperación de contraseña
comparten la identidad visual de la portada, sin cambiar sus rutas ni permisos.

No se modificaron modelos, migraciones, roles ni autorizaciones.
Los estudios de pacientes no se consultan ni se muestran en la portada.
La aplicación posterior del diseño a la gestión administrativa está documentada
en [Panel de odontólogos](panel-odontologos.md).
No se agregaron dependencias, fuentes remotas, analítica, mapas embebidos ni CDNs.

## Dónde modificar cada cosa

| Archivo | Responsabilidad |
| --- | --- |
| `apps/core/views.py` | Vista pública `landing`, sin consultas a modelos. |
| `apps/core/urls.py` | Ruta con nombre `core:landing`. |
| `templates/core/landing.html` | Textos, servicios, preguntas y contacto de la portada. |
| `templates/core/public_base.html` | Cabecera, enlaces de acceso, mensajes y pie compartidos. |
| `templates/core/auth_base.html` | Estructura compartida de registro y recuperación. |
| `templates/core/includes/form_field.html` | Campos con etiquetas, errores, ayuda y visibilidad de contraseña. |
| `templates/core/includes/brand.html` | Presentación del isotipo y nombre D.O.C. |
| `templates/core/includes/icon.html` | Iconos SVG locales acompañados por texto. |
| `templates/registration/login.html` | Presentación del login, errores, CSRF y campo `next`. |
| `apps/usuarios/templates/usuarios/odontologo_autoregistro.html` | Formulario profesional y aviso de habilitación pendiente. |
| `apps/usuarios/forms.py` | Autocompletado y ayuda de contraseña según los validadores configurados. |
| `templates/registration/password_reset_*.html` | Solicitud, confirmación, nueva contraseña, enlace inválido y finalización. |
| `static/core/css/public.css` | Colores en `:root`, componentes y tamaños responsive. |
| `static/core/js/public.js` | Menú móvil y mostrar/ocultar contraseña. |
| `static/core/images/` | Recursos institucionales del sitio. |
| `apps/core/tests/test_landing.py` | Pruebas específicas de portada y acceso. |
| `apps/core/tests/test_public_forms.py` | Presentación, CSRF y flujos de registro y recuperación. |

El diseño público tiene una base independiente de `templates/base.html`.
Registro y recuperación usan `core/auth_base.html`. La gestión administrativa
de odontólogos usa `core/admin_base.html`, que reutiliza los estilos
comunes y agrega `admin.css`. Los paneles propios de odontólogos y pacientes no
fueron rediseñados en esta entrega.

El administrador entra directamente en `/odontologos/`; no existe una pantalla
intermedia de Inicio. La URL anterior `/admin-centro/` redirige a ese listado.

## Identidad y procedencia del contenido

- Paleta tomada de las referencias de marca adjuntas: azul petróleo, turquesa,
  coral y fondos claros. El turquesa oscuro de textos mejora su legibilidad.
- `doc-isotipo.svg` es una adaptación vectorial del isotipo de referencia para
  evitar el fondo negro o el damero incrustado de los JPEG. Conviene reemplazarlo
  por el archivo vectorial oficial si el cliente lo proporciona.
- `doc-equipo-original.jpg`: imagen institucional `ppt/media/image6.jpeg` de
  **MARKETIN (1).pptx**. Se conserva el archivo original; el encuadre del equipo
  se hace con CSS, sin modificar el folleto fuente.
- `doc-radiografias.jpg`: `ppt/media/image1.jpeg` del mismo PowerPoint.
- `doc-planificacion.png`: conversión a PNG de `ppt/media/image2.tiff` del mismo
  PowerPoint, sin alterar su contenido visual.
- Servicios contrastados con **MARKETIN (1).pptx** y el folleto de D.O.C. incluido
  en **Publicidad CRO-DOC.pptx** (`image9.jpeg` e `image10.jpeg`).
- La dirección, teléfono, interno, correo y nombres profesionales proceden de
  esos folletos. Se utiliza el correo de D.O.C. (`doc.imagenes@gmail.com`), no el
  correo de C.R.O. que también aparece en la presentación.
- No se incluyeron horarios, testimonios, estadísticas ni resultados clínicos
  inventados. El sitio se concentra en diagnóstico por imágenes, no en anunciar
  como propios todos los tratamientos de la clínica C.R.O.

Antes de publicar, el cliente debe confirmar la vigencia de los datos de contacto,
servicios, nombres y versión del logotipo, y la autorización para usar las imágenes
del material promocional. No se utilizaron archivos de estudios de la base real.

## Comportamiento y accesibilidad

- Inicio público para visitantes y usuarios autenticados.
- Acceso privado mediante las rutas y permisos que ya existían.
- Menú móvil con `aria-expanded`, cierre al navegar y mediante Escape.
- Sin JavaScript, la navegación permanece visible; los acordeones usan
  `details/summary` nativos y el formulario sigue funcionando.
- Etiquetas de campos, errores visibles, navegación por teclado, enlace para
  saltar al contenido y respeto por movimiento reducido.
- La contraseña solo cambia de visibilidad al pulsar Mostrar/Ocultar: no se
  guarda en el navegador ni se transmite mediante JavaScript.
- La redirección `next` se conserva y Django sigue rechazando destinos externos.
- El autorregistro sigue creando odontólogos pendientes e inactivos hasta que
  el centro los habilite. No se agregó autorregistro de pacientes.
- La recuperación muestra una confirmación genérica, sin revelar si un correo
  está registrado. Django conserva la validación, caducidad y uso único del enlace.
- En desarrollo, el correo se muestra en la terminal mediante el backend de
  consola; no se envían mensajes reales. El envío de producción debe configurarse aparte.
- El mapa se abre mediante un enlace externo; no carga servicios de terceros
  hasta que la persona decide abrirlo.

## Verificación

```powershell
.\.venv\Scripts\python.exe -B manage.py test --settings=config.settings.test
.\.venv\Scripts\python.exe -B manage.py check
.\.venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run --settings=config.settings.test
```

La suite completa pasó con 72 pruebas: 39 anteriores, 10 de portada, 9 de
formularios públicos, 12 del panel administrativo y 2 de entrada directa del
administrador. No hay cambios
de modelos pendientes de migración. Las pruebas usan SQLite aislado y usuarios
sintéticos; no escriben sobre el esquema MySQL de desarrollo.

Prueba manual sugerida:

1. Abrir `/` sin iniciar sesión y recorrer los enlaces de la cabecera.
2. Abrir y cerrar los detalles de servicios y las preguntas frecuentes.
3. Repetir en celular, comprobar el menú y cerrarlo con Escape.
4. Abrir Acceder a estudios; probar Mostrar/Ocultar, errores y recuperación.
5. Con una cuenta de prueba habilitada, comprobar la redirección a su panel.
6. Confirmar que una visita anónima no puede abrir paneles privados.
7. Revisar el registro en escritorio y celular, las ayudas y los errores;
   comprobar que una cuenta nueva no puede ingresar antes de ser habilitada.
8. Recorrer recuperación, confirmación, nueva contraseña y finalización, y
   comprobar la alternativa para un enlace inválido, vencido o ya utilizado.

## Nota sobre la base local durante esta implementación

El 03/09/2026 la conexión MySQL configurada devolvió una lista vacía de tablas y
el navegador informó que `sisetma.django_session` no existía. No se modificó el
`.env` ni se crearon o borraron tablas en ese esquema. La revisión visual se hizo
en `http://127.0.0.1:8001/` con una base SQLite temporal fuera del repositorio.

Esa vista previa no contiene datos clínicos reales y no reemplaza la conexión normal.
Se creó allí una cuenta de demostración `admin_demo`, con rol de administrador
del centro, para ingresar a `/admin-centro/`. No es un superusuario de Django
ni tiene acceso a `/admin-django/`. Su contraseña se entregó por separado y no
se guarda en el repositorio. Se conservó la cuenta pendiente que ya existía en
esa base, sin habilitarla ni cambiar sus credenciales.
Antes de probar usuarios reales hay que verificar la instancia/esquema elegidos
y el estado de sus migraciones; no corresponde borrar ni recrear una base con
datos para probar este diseño.
