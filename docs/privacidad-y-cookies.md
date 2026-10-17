# Privacidad, cookies y créditos públicos

Fecha: 16/10/2026. Documentación de implementación; no constituye asesoramiento legal ni revisión jurídica.

## Alcance y referencias

Extensión pública en modo Read, conforme a `.impeccable/surfaces/privacidad-publica.md`.
Se contrastó con `PRODUCT.md`, `DESIGN.md` y `docs/diseno/landing-institucional-2026-10-15.md`.
La ruta `/politica-de-privacidad/` (`core:privacy`) presenta información sin consultar datos clínicos.
Se agregan enlaces desde pies públicos y de acceso, aviso técnico y créditos compartidos.
No hay cambios de autenticación, modelos, permisos, lógica clínica, migraciones ni datos SQL.

## Archivos modificados y creados

| Estado | Archivo |
|---|---|
| Modificado | `apps/core/urls.py` |
| Modificado | `apps/core/views.py` |
| Modificado | `templates/core/auth_base.html` |
| Modificado | `templates/core/landing.html` |
| Modificado | `templates/core/public_base.html` |
| Nuevo | `apps/core/privacy.py` |
| Nuevo | `apps/core/tests/test_privacy.py` |
| Nuevo | `frontend/public/browser-tests/privacy.spec.js` |
| Nuevo | `frontend/public/browser-tests/teardown.js` |
| Nuevo | `playwright.public.config.js` |
| Nuevo | `static/core/css/privacy.css` |
| Nuevo | `static/core/js/cookie_notice.js` |
| Nuevo | `templates/core/includes/cookie_notice.html` |
| Nuevo | `templates/core/includes/landing_footer.html` |
| Nuevo | `templates/core/includes/team_credits.html` |
| Nuevo | `templates/core/privacy.html` |
| Nuevo | `tests/public_browser_server.py` |
| Nuevo | `docs/privacidad-y-cookies.md` |

El contrato y las capturas de `.impeccable/` son evidencia local ignorada por Git.

## Contenido y evidencia

La política pública se reescribió por indicación del usuario: lenguaje institucional
para pacientes y odontólogos, sin detalles de arquitectura ni pendientes internos.
Contiene nueve secciones: Introducción, Información que recopilamos, Cómo utilizamos
la información, Acceso a la información, Estudios y archivos clínicos, Seguridad y
confidencialidad, Cookies, Conservación de información y Contacto.
El texto del artículo tiene 488 palabras y ocupa dos páginas A4 en la prueba de impresión.
No identifica cookies, proveedores ni mecanismos internos; conserva contacto y fecha.

El inventario técnico y sus fuentes se mantienen únicamente en esta documentación:
Fuentes: `Usuario` y `Odontologo` en `apps/usuarios/models.py`; `Paciente` en `apps/pacientes/models.py`;
`Estudio` e `ImportacionEstudio` en `apps/estudios/models.py`; `Archivo` en `apps/archivos/models.py`;
`Autorizacion` en `apps/accesos/models.py`; `LogActividad` en `apps/auditoria/models.py`;
y análisis de cargas en `apps/estudios/services/importador.py`.
El código distingue originales con metadatos, revocación de accesos, eliminación lógica y purga física;
la página pública explica sus consecuencias generales sin describir esos mecanismos.
La recuperación de contraseña existe; el envío efectivo depende de configurar el correo.
`apps/notificaciones/README.md` describe intención y `Estudio.notificar_destinatarios()` sigue vacío:
no se garantiza el envío de notificaciones de estudios.
Contacto heredado: doc.imagenes@gmail.com; 0370 442-2272, interno 2; Mitre 479, Formosa.

## Inventario de cookies

`apps/core/privacy.py::application_cookies()` conserva el inventario interno de nombres,
duración y opciones desde settings. La vista pública ya no lo pasa al template.
Los valores actuales proceden de los defaults de Django en `django/conf/global_settings.py`,
sin overrides de esos nombres o edades en los settings inspeccionados.
La lista omite CSRF si `CSRF_USE_SESSIONS=True` y messages si el backend no utiliza cookies.

| Cookie actual | Uso y origen | Duración actual | Consecuencia de bloqueo |
|---|---|---|---|
| `sessionid` | Propia, técnica: identifica la sesión | `SESSION_COOKIE_AGE=1209600`: 14 días; puede renovarse | No se mantiene el acceso autenticado |
| `csrftoken` | Propia, técnica: protección CSRF | `CSRF_COOKIE_AGE=31449600`: 364 días; puede renovarse | Los formularios protegidos pueden rechazarse |
| `messages` | Propia, técnica: avisos temporales | De sesión, sin `max-age` ni caducidad persistente | Pueden perderse avisos tras redirecciones |

`MESSAGE_STORAGE` usa `django.contrib.messages.storage.fallback.FallbackStorage`.
`CookieStorage` emite `messages` cuando hay avisos; el fallback puede utilizar la sesión.
La cookie se retira al consumir los mensajes; la restauración del navegador puede conservar sesiones.
Evidencia adicional: `django/contrib/messages/storage/cookie.py` y `apps/core/tests/test_privacy.py`.
No se encontraron cookies de analítica o publicidad en la implementación revisada.
`production.py` exige cookies Secure; la configuración efectiva del despliegue sigue pendiente.

## Aviso y almacenamiento del navegador

«Entendido» oculta el aviso informativo; no acepta, rechaza ni modifica cookies técnicas.
El script guarda `localStorage.doc_cookie_notice_v1='seen'`, sin TTL, y sincroniza el cierre entre pestañas.
Con almacenamiento bloqueado permite cerrar esa vista; el aviso puede reaparecer al navegar.
Sin JavaScript permanecen la política, los enlaces y el mensaje `noscript`.
No es un diálogo modal: no captura el foco; al cerrar desde él devuelve el foco al contenido sin desplazarlo.
La altura del aviso reserva espacio inferior para la lectura.
Son registros distintos de las cookies las preferencias existentes `doc_file_view_mode`,
`doc_tutorial_admin_visto` y `doc_tutorial_derivante_visto`, también sin vencimiento automático definido.
La selección de derivante usa `sessionStorage`, con clave `doc:derivante:<adminId>:<importacion>`;
su ámbito es la sesión de la pestaña, no una cookie ni una preferencia permanente del aviso.

## Herencia visual y créditos

Se preservan marca, azul D.O.C., superficies claras y separadores del sistema existente.
Manrope local se hereda de la landing pública; Segoe UI sigue siendo la referencia clínica de `DESIGN.md`.
La lectura usa columna de hasta 70ch, índice lateral en escritorio y apilado en móvil.
La impresión omite navegación, footer y aviso, y ajusta el documento para A4 legible.
Las diferencias locales no redefinen tokens globales ni autorizan reparar desajustes históricos.
`PRODUCT.md`, `DESIGN.md` y `.impeccable/design.json` se preservan.
El footer compartido de landing y política incluye `templates/core/includes/team_credits.html`.
Único punto de edición de nombres: `[NOMBRES DEL EQUIPO]`, placeholder intencional pendiente.

## Verificación y límites

```powershell
.\.venv\Scripts\python.exe manage.py test apps.core.tests.test_privacy.PrivacyPublicTests apps.core.tests.test_landing.LandingPublicaTests apps.core.tests.test_public_forms.FormulariosPublicosPresentacionTests --settings=config.settings.test_mysql -v 1
npx.cmd playwright test --config=playwright.public.config.js
.\.venv\Scripts\python.exe manage.py check --settings=config.settings.test_mysql
```

- Django: 21 SimpleTestCase aprobados (9 privacidad, 9 landing, 3 presentación); sin acceso a BD ni SQLite.
- Navegador tras la reescritura: exit 0; 7 pruebas aprobadas en 14,9 s, Edge headless.
- Cobertura: teclado/foco, cierre y persistencia, almacenamiento bloqueado, navegación sin JS,
  CSRF independiente del aviso, ausencia de peticiones de terceros, sincronización entre pestañas
  y ausencia de overflow a 1440, 390 y 320px.
- Se verifica la estructura de nueve secciones, la ausencia de tecnicismos en el
  texto público y una impresión de 488 palabras en dos páginas A4 (máximo permitido: tres).
- Dos rondas acotadas de capturas: se corrigieron la cascada del tamaño del índice y el solapamiento de cabecera.
  Evidencia final en `.impeccable/review/privacy-public/`, ignorada por Git.
- `playwright.public.config.js` usa `tests/public_browser_server.py` para páginas públicas sin consultas SQL,
  en loopback `127.0.0.1:8767`; el teardown cierra ese servidor mediante endpoint con token de prueba.
- `manage.py check` no completó: MySQL local detenido, error 2002 / TCP 10061.
  No se inició ni modificó el servicio; este fallo no invalida las pruebas públicas sin SQL.
- Context loader y detector de Impeccable fallaron con `cache_directory_failed`;
  se leyó el contexto directamente y ninguno se contabiliza como validación aprobada.
- Revisión de la versión original: **SHIP** en su alcance de implementación.
  El usuario pidió después simplificar el contenido; ese veredicto anterior no
  certifica la redacción actual. Nueva revisión independiente de texto y capturas:
  **SHIP** para la versión breve, sin hallazgos materiales en ese alcance. Se
  confirmó la estructura, ausencia de tecnicismos y pendientes visibles, contacto
  y herencia visual. La revisión no repitió las pruebas ni constituye validación jurídica.
- Documentación contrastada independientemente con el sistema incumbente; no se modificó su definición global.
- No se certifican flujos clínicos con BD, autenticación real, correo, MinIO ni una auditoría WCAG completa.

## Pendientes antes de producción

Confirmar responsable formal y canal de privacidad; proveedores de alojamiento, almacenamiento y correo;
ubicación y condiciones de tratamiento; conservación de fichas, estudios, auditoría, logs y respaldos;
procedimientos de corrección/eliminación y configuración efectiva de seguridad.
Completar nombres del equipo en el include indicado.
Revisar política e inventario si cambian settings, servicios o almacenamiento del navegador.
No se afirman plazos legales, proveedores definitivos ni garantías de cumplimiento normativo.
