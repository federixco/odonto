# D.O.C. — familia de acceso de claridad clínica

Fecha: 6 de octubre de 2026. Estado: implementada, verificada y con veredicto independiente **ship**; pendiente de validación visual del usuario antes de extenderla a otras pantallas.

El pedido actual toma la landing como aprobada y autoriza login, registro profesional y recuperación. Esta familia continúa «claridad clínica» en modo **Operate**: el formulario y su resultado lideran; la marca y la ayuda contextual sostienen la confianza. Es una extensión precisa con seed heredado `ceada702`, sin torneo, comp nueva ni nueva identidad. El contrato local de seis bloques está en `.impeccable/surfaces/templates-core-auth-base-html.md`.

La implementación conserva autenticación, permisos, rutas, validadores y respuestas del servidor. No alcanza dashboard, administración, portales, visor, landing ni formularios compartidos de otras tareas. No incorpora prestaciones, promesas, fotografías o activos de marca nuevos.

## Composición y recorrido

Todas las etapas comparten cabecera blanca reducida a marca y «Volver al sitio», un único h1 de tarea y pie compacto con copyright, ingreso a la cuenta y Formosa. Se reutilizan logo, wordmark y SVG funcionales existentes. El plano blanco del formulario domina a la izquierda; la ayuda permanece a la derecha en escritorio y sigue a los campos en móvil.

| Pantalla o estado | Comportamiento conservado y presentación |
| --- | --- |
| Login | Un formulario de usuario y contraseña para profesionales y pacientes. El panel navy separa solicitud profesional, habilitación previa y orientación para pacientes. Recuperación queda junto al formulario. La sesión existente muestra el aviso real y acceso a la cuenta. |
| Registro profesional | Aviso de habilitación pendiente antes de los campos y orientación para pacientes. Dos grupos nativos: datos profesionales y acceso a la cuenta. El panel navy explica completar, esperar habilitación e ingresar. El alta real crea una cuenta `PENDIENTE`, informa el resultado y el login continúa rechazando su ingreso hasta la habilitación. |
| Solicitud de recuperación | Correo asociado a la cuenta y acción de enviar enlace. La ayuda usa superficie fría; ofrece contacto si la persona no recuerda el correo. |
| Revisar correo | Conserva el mensaje condicional «Si el correo corresponde a una cuenta habilitada…», sin revelar existencia de una cuenta. Ofrece volver a login o solicitar otro enlace. |
| Nueva contraseña | Dos campos, requisitos del servidor y acción de guardar. Las ayudas se mantienen vinculadas a su campo. |
| Enlace inválido | Título y aviso propios: la contraseña no se modificó. Ofrece solicitar un enlace nuevo. |
| Recuperación completa | Confirma el cambio después del resultado real y ofrece iniciar sesión. |

## Lenguaje visual y adaptación

La familia mantiene Segoe UI y el wordmark Arial heredado. Usa azul D.O.C. `#004b64`, turquesa de interacción `#007d85`, tinta `#163c48`, secundario `#50666f`, líneas `#d7e3e7`, borde de campo `#a9c0c8`, superficie fría `#edf6f6` y blanco. Los enlaces sobre panel navy y su foco usan `#8ae0e4`; sobre superficie fría usan navy. El breve acento coral `#f66d68` continúa la marca. Error, advertencia y deshabilitado conservan tonos semánticos existentes, acompañados por texto explícito.

| Elemento | Implementación local |
| --- | --- |
| Título de tarea | 40 / 34 / 30 px en escritorio, hasta 860 px y hasta 600 px; peso 650, línea 1.15 y tracking −.025em. |
| Lectura y campos | Base de 16 px y línea 1.6; campos de 16 px y línea 1.5. Introducción limitada a 58ch. |
| Etiquetas y acciones | Etiquetas de 14 px, peso 600; acción principal de 15 px, peso 600. Ayudas de 14 px; encabezados de ayuda de 20 px. |
| Controles | Campos y acción principal de mínimo 48 px; mostrar contraseña y enlaces principales de mínimo 44 px. Campos y botones con radio de 6 px; avisos de 8 px. |
| Foco y movimiento | Outline de 3 px, offset de 3 px; claro sobre navy y semántico en resumen de errores. Hover sin desplazamiento ni sombra; transición de 150 ms. `prefers-reduced-motion` elimina transiciones y animaciones. |

El contenedor llega a 1120 px con márgenes laterales de 40 px. El layout usa columnas `1.2fr / .85fr`, separación de 80 px y padding vertical de 64 / 80 px. Hasta 1100 px la separación baja a 48 px; hasta 860 px pasa a una columna, contenedor máximo de 640 px y márgenes de 24 px. Hasta 600 px los márgenes son 16 px, los campos de registro se apilan y el pie queda en columna. A 768 px el registro conserva pares de campos dentro de la columna de tarea. Las grillas permiten encoger su contenido con `minmax(0, 1fr)`.

La profundidad depende de planos navy, blancos y fríos y de líneas finas. Esta composición y su rampa tipográfica pertenecen a acceso; no reemplazan los tokens compactos de confirmación ni la escala editorial de la landing.

## Campos, errores y mejora progresiva

Los templates renderizan los campos Django originales: nombres, valores, atributos `required`, condición opcional, `autocomplete`, CSRF, destinos y `next` permanecen bajo los contratos existentes. Teléfono conserva su condición opcional. El include exclusivo `access_field.html` evita alterar `form_field.html` y otras superficies.

Los errores reales permanecen junto al campo; el resumen se presenta como alerta enfocada tras la respuesta del servidor. `access.js` relaciona cada error existente mediante `aria-invalid` y `aria-describedby` y enfoca ese resumen. No intercepta POST ni agrega validación. Los requisitos de contraseña vienen del servidor en `details/summary`; se abren cuando el campo de contraseña correspondiente tiene errores.

Mostrar/ocultar contraseña reutiliza `public.js` intacto. Sin JavaScript, su botón permanece oculto y los campos, envío, ayudas nativas y validación del navegador siguen disponibles. La mejora progresiva no cambia el resultado de autenticación o recuperación.

## Fuentes para mantenimiento

| Fuente | Responsabilidad |
| --- | --- |
| `templates/core/auth_base.html` | Shell exclusivo de acceso; carga `access.css` con versión `claridad-clinica-1` y `access.js`. Hereda `public_base.html`. |
| `templates/core/includes/access_field.html` | Etiqueta, condición opcional, password toggle, ayuda y errores reales por campo. |
| `templates/registration/login.html` y `apps/usuarios/templates/usuarios/odontologo_autoregistro.html` | Tareas y ayudas de roles; no trasladar mensajes de habilitación a reglas nuevas. |
| `templates/registration/password_reset_{form,done,confirm,complete}.html` | Etapas Django de recuperación y bifurcación `validlink`. |
| `static/core/css/access.css` | Overrides bajo `.access-page`, composición, reflow, foco y estados. |
| `static/core/js/access.js` | Relación de errores existentes y foco del resumen. |

La autoridad visual comparada es `docs/diseno/direccion-visual-propuesta.md`, `DESIGN.md`, `PRODUCT.md`, `docs/diseno/landing-claridad-clinica.md` y las capturas aprobadas de `.impeccable/review/landing-bolder/`. Para futuros cambios, conservar estos contratos y comprobar las etapas reales; no convertir los mensajes de servidor en éxitos anticipados.

La vista previa Django real permite revisar [login](http://127.0.0.1:8001/auth/login/), [registro profesional](http://127.0.0.1:8001/registro-odontologo/) y [recuperación](http://127.0.0.1:8001/auth/password_reset/). Se verificaron GET 200, formulario POST y carga de la hoja nueva. Las pruebas con envíos se hicieron en el entorno aislado descrito abajo.

## Verificación y límites

La evidencia de entrega está en `.impeccable/review/access/verification.json`, `review.md` y 29 capturas finales. Cubre siete pantallas/estados a 1440 y 390 px; registro a 320 y 768 px; login a 1024 px; errores de login y registro en escritorio y móvil; correo inválido, contraseñas distintas, ayuda abierta, registro sin JavaScript, aviso de alta y rechazo de cuenta pendiente, cambio real de contraseña y sesión existente.

El lote registra cero fallos, overflow horizontal y referencias ARIA rotas; campos de 16 px y controles principales de al menos 44 px. Se comprobaron foco de errores, CSRF y atributos nativos. La comparación SHA de 13 fuentes protegidas confirmó landing, fuentes públicas compartidas, backend y correos intactos. Pasaron 32 pruebas existentes de `apps.core.tests.test_landing`, `apps.core.tests.test_public_forms` y `apps.usuarios.tests.test_views`, además de `git diff --check`.

Los helpers locales `.local/access-check.mjs` y `.local/access-qa-server.py` usan WSGI Django con SQLite en memoria y correo `locmem`; sus envíos no escriben en la base clínica ni envían correo real. El servidor de QA en 8002 es temporal. Capturas, contratos y helpers permanecen en carpetas locales ignoradas; la aplicación no depende de ellos. No se crearon commits ni pushes.

La revisión independiente completa abrió las 29 capturas finales, cuatro baseline y tres de landing; registró correspondencia con el contrato, reflow como adaptación prevista y un único arreglo de contraste. El veredicto final **ship** puntuó exclusivamente ese arreglo como **resolved**, con **remaining: clear**; el contraste final de enlaces navy sobre superficie fría mide 8.726:1. Se ejecutó un solo detector: 26 observaciones advisory —13 de color y 13 de tamaño— y cero hard. El análisis estático no resuelve includes y static de Django; sus valores inferidos se contrastaron con fuente y render.

Estos resultados cubren los casos medidos, no una auditoría completa de accesibilidad. No se verificó zoom real al 200 % ni un techo externo QualityBar; no hubo comp nueva. La validación visual de esta familia sigue siendo necesaria antes de extenderla.

## Comparación con el sistema y drift preservado

Paleta principal, colores semánticos, radios de control y aviso, superficies planas y foco continúan el sistema registrado. Los tamaños 40/34/30 y la composición formulario/ayuda son decisiones locales de acceso; sus diferencias con la rampa compacta de confirmación no se elevan a tokens globales. Los tonos auxiliares `#c8ecec`, `#8aabb4`, `#edf3f5`, `#d1edf2`, `#328498`, `#8ae0e4` y el activo `#002e40` ya tienen usos heredados; su cobertura parcial en frontmatter o snippets es preexistente.

`PRODUCT.md`, el Overview de `DESIGN.md` y el documento de landing todavía registran pendientes históricos de la amplificación v3 y marketing; el overview del sidecar conserva una descripción pública anterior. El pedido actual autoriza esta familia desde la landing aprobada. Este documento deja constancia de esa autorización sin reescribir los antecedentes ni declarar una identidad global aprobada.

No se modificaron `DESIGN.md`, `PRODUCT.md`, sus tokens ni `.impeccable/design.json` en esta entrega de acceso. Tampoco se normalizaron estilos compartidos distintos fuera del scope. El descriptor diminuto del wordmark, la cobertura incompleta de tonos auxiliares y los estilos heredados fuera de acceso se preservan sin canonizarlos como reglas nuevas.
