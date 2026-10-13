# D.O.C. — landing de claridad clínica, v3

Fecha: 5 de octubre de 2026. Estado: amplificación v3 implementada y revisada, pendiente de validación visual del usuario. El usuario aprobó la dirección «claridad clínica» y manifestó que le gusta la base v2; pidió más personalidad y presencia. Esa aprobación permite este refinamiento de la landing y no equivale a aprobar su resultado v3 ni una identidad global.

La prioridad permanece en **conocer servicios y contactar al centro**, con acceso a estudios siempre visible. V3 conserva estructura, marca, familia sans, colores, fotografías, contenido y destinos; amplifica hero, transiciones entre superficies, jerarquía fotográfica y ritmo editorial. La expresión busca un centro profesional, moderno y creíble mediante material institucional real. No incorpora tarjetas SaaS, gradientes, vidrio, métricas, testimonios, prestaciones ni promesas inventadas.

El contrato local de seis bloques está en `.impeccable/surfaces/templates-core-landing-html.md`. Es una extensión ordinaria del mundo elegido, con seed heredado `ceada702`, sin nueva elección de dirección ni comp. Sólo se aplica a la landing; no autoriza cambios en otras pantallas, framework, backend, rutas, permisos o lógica de negocio.

## Composición implementada

- Encabezado blanco con marca, navegación y acceso a estudios visible también con el menú móvil cerrado.
- Hero azul con el énfasis «un buen diagnóstico» en el tono turquesa claro existente. Una línea de 1 px ordena la banda de explicación y acciones. La fotografía del equipo cruza el cierre azul con mayor presencia; su pie azul queda integrado y lleva un acento coral de 2 px, sin tarjeta blanca flotante ni radio.
- Servicios en dos columnas desiguales, con radiografías primero como imagen y explicación, y tomografía como explicación e imagen. El desplazamiento vertical de tomografía produce un catálogo escalonado. Complementarios cierra transversalmente con una línea de 1 px, sin placa de fondo suave; todas las prestaciones permanecen visibles.
- Centro sobre superficie fría con isotipo existente y profesionales reales. Los nombres de Dra. María Luisa Stechina y Dr. Pedro Eduardo Morales ganan jerarquía y se separan con divisores finos.
- Acceso como composición continua azul y blanca: introducción, acción blanca y recuperación en azul; ayuda nativa sobre blanco. No hay tarjeta flotante, borde exterior ni radio. Se conserva la habilitación profesional pendiente y la vinculación de la cuenta del paciente a sus estudios.
- Contacto final azul con título reforzado y los datos existentes de dirección, teléfono e interno, correo y ubicación; pie blanco con navegación breve.

El comparador de fuente contra `.local/landing-bolder-before/landing.html` normaliza whitespace, el span del h1 y la versión de CSS: confirma la conservación de textos, condiciones de autenticación y destinos del inicio de esta iteración. La comparación renderizada confirma enlaces, imágenes y alt idénticos. Hay un h1 y una aparición del teléfono y del correo en la landing; permanecen las tres familias de estudios.

## Lenguaje local y adaptación

Segoe UI continúa la sans existente y el wordmark conserva Arial. Azul `#004b64`, turquesa de interacción `#007d85`, tinta `#163c48`, secundario `#50666f`, líneas `#d7e3e7`, superficie suave `#edf6f6`, blanco y colores auxiliares ya presentes sostienen la composición. El énfasis del hero y la recuperación usan `#8ae0e4`; el coral `#f66d68` del isotipo se aplica al acento del pie fotográfico. La comparación de literales contra el CSS v2 no encontró colores nuevos. No se añadieron fuentes, radios, sombras ni activos.

La jerarquía pública sigue siendo local a esta superficie:

| Rol | Implementación en v3 |
| --- | --- |
| h1 | `clamp(44px, 4.5vw, 64px)`, peso 650, línea 1.08; 48 px bajo 860 px, 38 px bajo 600 px con línea 1.12 y 36 px hasta 360 px. Rampa intacta. |
| h2 de servicios y contacto | 48 / 40 / 30 px en escritorio, tablet y móvil; valores de la rampa existente, peso 650 y línea 1.15. |
| Otros h2 | 40 / 34 / 30 px; peso 650 y línea 1.15. |
| Títulos de servicios | 34 / 28 / 24 px; complementarios usa 28 px en escritorio y 24 px en móvil. |
| Pie del equipo | 40 / 34 / 28 / 20 px según los cortes de 1100, 860 y 600 px. |
| Profesionales | 24 px en escritorio y 18 px bajo 1100 px. |
| Lectura y acciones | Cuerpo base de 16 px, textos de 15–17 px y línea base 1.6; acciones de 15 px y peso 600. Los títulos auxiliares conservan tamaños según su función. |

El contenedor llega a 1220 px, con márgenes laterales de 40 px, 24 px bajo 860 px y 16 px bajo 600 px. Servicios usa columnas de proporción 1 / 1.1 y separación de 80 px en escritorio, reducida en tablet. Tomografía se desplaza 64 / 40 / 0 px; las columnas se apilan bajo 600 px. La imagen de radiografías se muestra a 340 px en escritorio dentro de la superficie fría; conserva su fuente de 316 × 260 px y pasa a 300 px en móvil.

El encuadre del equipo usa ventanas de 400 / 340 / 300 px. La imagen se presenta a 760 / 640 / 560 px, con desplazamiento superior de −325 / −290 / −255 px en escritorio, tablet y móvil. El pie pasa debajo de la imagen en móvil. El isotipo del centro mide 104 px en escritorio, 80 px bajo 1100 px y se oculta bajo 860 px; el texto y los profesionales permanecen. Centro y acceso terminan en una columna, y contacto se apila bajo 860 px.

Los botones mantienen 48 px, navegación y enlaces principales al menos 44 px y radios de control de 6 px. Fondos contrastantes, fotografía y líneas finas aportan profundidad. Hover sin desplazamiento, transiciones de 150 ms y foco de 3 px con offset de 4 px, claro sobre azul. Se respeta movimiento reducido. El menú móvil abre en el flujo del encabezado; Escape lo cierra y devuelve el foco. Sin JavaScript, la navegación queda disponible. Las anclas contemplan el encabezado sticky y la ayuda usa `details/summary` nativos.

## Fuentes, fotografías y aislamiento

Los cambios de interfaz de v3 están en `templates/core/landing.html` y `static/core/css/landing.css`. La hoja adicional se carga sólo en la landing, con versión de caché `claridad-clinica-3`; sus overrides quedan bajo `.landing-page` y clases propias. El template añade el span del h1 y concentra cinco etiquetas Django previamente multilínea en una línea para corregir su parseo, sin cambiar expresiones ni condiciones. Se reutilizan `public_base.html`, `public.css`, `public.js`, `brand.html` y los SVG locales sin modificaciones en esta iteración.

Las tres fotografías institucionales se conservaron sin editar píxeles ni crear assets. Su procedencia permanece en metadatos:

| Archivo en `static/core/images/landing/` | Fuente documentada |
| --- | --- |
| `doc-equipo-original.jpg` | `MARKETIN (1).pptx`, `ppt/media/image6.jpeg`. |
| `doc-radiografias.jpg` | Mismo PowerPoint, `ppt/media/image1.jpeg`. |
| `doc-planificacion.png` | Conversión existente de `ppt/media/image2.tiff` del mismo PowerPoint. |

El escaneo de procedencia registra tres rasters y ninguno sin metadatos. No se modificaron backend, rutas, permisos, lógica de negocio, otras pantallas ni framework. No se crearon commits ni se hicieron pushes en esta pasada.

## Verificación actual y límites

Pasaron 19 pruebas existentes de `apps.core.tests.test_landing` y `apps.core.tests.test_public_forms` con `config.settings.test`; `git diff --check` pasó. La evidencia actual está en `.impeccable/review/landing-bolder/verification.json`, `detector.json`, `review.md` y diez capturas finales. Helpers, capturas, brief, sidecar y skill permanecen locales en `.agents`, `.impeccable` y `.local`, carpetas ignoradas por Git por instrucción del usuario; la aplicación no depende de esos artefactos.

Las mediciones cubrieron 1440, 1280, 1024, 768, 390 y 320 px, además de menú móvil y navegación sin JavaScript. No detectaron overflow horizontal, referencias ARIA rotas, imágenes sin cargar, errores de consola ni controles principales inferiores a 44 px. Los textos medidos cumplieron contraste AA, incluido el énfasis del hero, pie fotográfico y enlaces. Se verificaron menú, Escape, devolución de foco, ancla de contacto sin obstrucción, ayuda nativa y movimiento reducido. Estos resultados describen los casos medidos y no equivalen a una auditoría completa de accesibilidad.

La vista previa v3 usa Django real en `http://127.0.0.1:8001/?v=3`. `GET /auth/login/` devolvió 200 con formulario, campos de usuario y contraseña y CSRF reales. No se enviaron credenciales, no se probó POST de autenticación ni el flujo autenticado completo, y no hubo escrituras en la base clínica ni migraciones. No se verificó zoom real al 200 %. Las pruebas históricas de otras versiones no se trasladan a esta entrega.

El detector se ejecutó una vez: 48 observaciones advisory, 18 de color y 30 de tamaño, sin hallazgos hard. Se contrastaron con fuentes y render real: el negro inferido al analizar includes Django sin resolver no describe el texto renderizado; la rampa pública local difiere de la compacta de confirmación. No se alteró el sistema global para silenciar observaciones. El catálogo externo QualityBar estuvo indisponible y no hubo comp nueva: no se afirma un techo externo verificado.

## Comparación con el sistema registrado

Se contrastaron template y CSS con `PRODUCT.md`, `DESIGN.md`, `.impeccable/design.json`, la propuesta visual y fuentes públicas compartidas; `confirmation.css` corrobora tonos auxiliares. La propuesta permite mayor libertad de composición y fotografía institucional con la misma familia y marca. DESIGN y sidecar registran confirmación: sus tokens permanecen intactos y la rampa de landing no se eleva a regla global.

| Aspecto | Evidencia y alcance |
| --- | --- |
| Paleta | Colores principales, hover `#003b50`, borde `#a9c0c8` y coral coinciden con el frontmatter. El activo `#002e40` es un uso local conservado. Todos los colores literales de v3 ya pertenecían al CSS v2. |
| Tonos auxiliares | Selección `#c8ecec`, scrollbar `#8aabb4` / `#edf3f5`, apoyo sobre azul `#d1edf2`, línea `#328498` y foco `#8ae0e4` aparecen en confirmación; algunos están en snippets o foco del sidecar, sin ser primitivos del frontmatter. Su cobertura documental incompleta es preexistente. |
| Tipografía | Misma Segoe UI y wordmark Arial. La rampa pública y línea 1.6 responden a la composición institucional; no sustituyen la rampa compacta de confirmación. El descriptor de marca de 6.5 px heredado, 6 px en móvil, no se canoniza como contenido. |
| Forma y estados | Controles de 6 px, bordes finos, superficies planas y foco turquesa continúan la gramática registrada. Escala, encuadre, offsets y composiciones sin tarjetas son aplicaciones locales. |
| Fuentes compartidas | `public.css` conserva tonos neutros, radios, sombras y tratamientos heredados distintos. Los overrides no normalizan otras páginas ni trasladan a gestión la composición pública. |

Se actualizó únicamente la última decisión de PRODUCT y la oración de estado de aprobación del Overview de DESIGN para registrar la dirección y base aceptadas y la validación de v3 pendiente. No se modificaron frontmatter, tokens, normativa ni sidecar. El overview del sidecar describe la interfaz pública anterior; la propuesta y otros pasajes de producto conservan pendientes históricos sobre marketing. Ese drift preexistente no se repara aquí ni valida v3. Tampoco se canonizan el descriptor diminuto de marca o los valores auxiliares incompletamente registrados.

## Revisión y estado de entrega

La revisión independiente completa abrió doce capturas válidas: dos anteriores y diez finales. Sus cinco apartados —persistencia, fidelidad, techo, arreglos materiales y elementos a conservar— registran correspondencia con THESIS, OWN-WORLD, STORY, FIRST VIEWPORT y FORM. El reflow es la adaptación prevista. No pidió arreglos visuales materiales y recomendó conservar diagnóstico destacado, franja del equipo, catálogo escalonado, profesionales reales y acceso azul/blanco, con servicios y contacto prioritarios.

Su disposición final fue **ship**. El veredicto cubre el lote revisado y las verificaciones registradas; no confirma el techo externo ni sustituye la validación visual del usuario. La dirección y base v2 están aceptadas; la amplificación v3 permanece pendiente de esa validación humana y no autoriza extenderla a otras pantallas.
