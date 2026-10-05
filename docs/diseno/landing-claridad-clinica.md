# D.O.C. — primera aplicación pública de claridad clínica

Fecha: 5 de octubre de 2026. Alcance: únicamente la landing institucional. El usuario aceptó el trabajo realizado; la extensión a otras pantallas requiere una nueva instrucción.

La instrucción vigente del usuario prioriza **conocer servicios y contactar al centro**. Esta implementación extiende la dirección de `docs/diseno/direccion-visual-propuesta.md` y los rasgos del prototipo registrados en `DESIGN.md`; no aprueba ni reemplaza el sistema global. La rampa compacta de confirmación corresponde a gestión; la propuesta institucional permite más libertad de composición y fotografía, manteniendo familia y marca.

La autorización es concreta: aplicar esa dirección únicamente a la landing, conservar fotografías, marca, familia sans y colores existentes, sin cambiar backend, rutas, permisos ni otras páginas. Esta autorización resuelve sólo la implementación institucional presente y no constituye aprobación duradera de una identidad global.

## Composición y contenido

- Encabezado con identidad, navegación institucional y acceso a estudios siempre visible, incluso con el menú móvil cerrado.
- Una introducción, dos acciones hacia contacto y servicios, y una banda del equipo fotografiado en el material institucional.
- Catálogo de tres familias en filas editoriales: radiografías digitales, tomografía 3D y estudios complementarios. Sus prestaciones quedan visibles sin abrir tarjetas.
- Presentación breve del centro y los dos profesionales existentes.
- Acceso y ayuda nativa diferenciada para odontólogos y pacientes. Se conserva la habilitación profesional pendiente y la vinculación de la cuenta del paciente; no se promete un alta automática.
- Contacto con dirección, teléfono e interno y correo existentes. Teléfono y correo aparecen una vez. Pie breve de navegación.

Se eliminaron la repetición de explicaciones institucionales, la cita ornamental, la tira superior de contacto y el FAQ separado. La información útil del FAQ queda junto al acceso; la planificación de implantes figura en tomografía y deja de repetirse entre complementarios. No se incorporaron métricas, testimonios, horarios ni servicios nuevos. Se preservan los nombres, contacto y catálogo de la landing anterior, con la procedencia registrada en `docs/landing-page.md`.

## Lenguaje implementado en esta superficie

La landing usa Segoe UI y el wordmark existente. Colores principales heredados: azul `#004b64`, turquesa de interacción `#007d85`, tinta `#163c48`, secundario `#50666f`, líneas `#d7e3e7`, fondo suave `#edf6f6`, blanco y canvas `#f4f7f8`. Turquesa y coral del isotipo se conservan. El foco usa turquesa y un tono claro sobre el panel azul.

Escala observada exclusiva de la landing: h1 56/48/46/36 px según ancho; h2 34/28 px; h3 de servicios 22 px; texto 15–17 px, base 16 px. Acciones principales de al menos 48 px y controles de navegación de 44 px. Radios de botones de 6 px, separadores finos, sin sombras añadidas ni animaciones de entrada. El pequeño descriptor del wordmark conserva su tratamiento de marca y no se utiliza para el contenido.

Contenedor de hasta 1220 px; márgenes laterales de 40 px en escritorio, 24 px bajo 860 px y 16 px bajo 600 px. Los servicios pasan de tres columnas a dos y luego a una. El menú móvil se abre en el flujo del encabezado; Escape lo cierra y devuelve el foco. Sin JavaScript, los enlaces permanecen disponibles. El desplazamiento a las anclas contempla el encabezado fijo. Se respeta movimiento reducido.

## Archivos y aislamiento

- `templates/core/landing.html`: composición, contenido y overrides de cabecera/pie.
- `static/core/css/landing.css`: hoja cargada sólo por la landing; estilos bajo `.landing-page` y sus clases propias.
- `templates/core/public_base.html`: bloques de herencia nuevos que conservan el contenido predeterminado para las demás páginas.
- `static/core/images/landing/`: tres copias institucionales con metadatos de procedencia.

`public.css`, `public.js`, login, registro, recuperación, pantallas internas, rutas, modelos, permisos y lógica de negocio conservan su implementación anterior a este trabajo. Los cambios preexistentes del prototipo de confirmación quedan fuera de esta entrega.

## Fotografías

Se mantienen los originales compartidos sin modificarlos. Las copias de uso exclusivo de la landing tienen las mismas dimensiones y los mismos píxeles decodificados, verificados con Pillow; sólo incorporan procedencia en metadatos. El encuadre del folleto del equipo se hace mediante CSS, sin retocar la fotografía.

| Archivo | Fuente documentada |
| --- | --- |
| `doc-equipo-original.jpg` | `MARKETIN (1).pptx`, `ppt/media/image6.jpeg` |
| `doc-radiografias.jpg` | Mismo PowerPoint, `ppt/media/image1.jpeg` |
| `doc-planificacion.png` | Conversión existente de `ppt/media/image2.tiff` del mismo PowerPoint |

Escaneo de procedencia: tres rasters, ninguno sin metadatos. No se generaron fotografías ni activos de marca.

## Verificación y límites

Pasaron 19 pruebas existentes de `apps.core.tests.test_landing` y `apps.core.tests.test_public_forms` con settings de test. Las comprobaciones de navegador cubrieron 1440, 1024, 768, 390 y 320 px, menú abierto, acceso autenticado sintético, ayuda abierta, navegación sin JavaScript y movimiento reducido. No se detectó desbordamiento horizontal, fotos sin cargar, controles principales menores de 44 px ni referencias ARIA rotas en los casos medidos.

`zoom-200.png` representa reflow equivalente a una ventana física de 640 px al 200%: viewport CSS de 320 px y escala 2. No es una prueba de zoom real del navegador ni de ampliación exclusiva del texto. La vista previa loopback renderiza templates reales sin base clínica y no valida un flujo de autenticación real. No se activaron enlaces externos de correo, teléfono o mapa.

Se utilizaron once capturas y mediciones de navegador. El servidor de vista previa se reinició antes de las capturas finales para descartar templates en caché. El detector se ejecutó una vez: 29 advertencias informativas (8 de color y 21 de tamaño); ninguna de severidad superior. Los tamaños corresponden a la jerarquía pública de esta página; los tonos auxiliares se documentan como usos locales. El negro inferido en includes de Django no corresponde al color renderizado. No se modificó el sistema global para silenciar advertencias.

No hubo comp aprobada ni referencia externa disponible del catálogo QualityBar; el criterio de fidelidad es la dirección institucional fijada por el usuario y el material local. La revisión independiente y la comparación documental registran su alcance por separado; no sustituyen la validación humana ni autorizan extender el diseño.

## Comparación con el sistema registrado

La comparación documental se realizó sobre `landing.css`, `landing.html`, `public_base.html`, la base y el script públicos, `confirmation.css`, `DESIGN.md` y `.impeccable/design.json`. Estos dos últimos registran exclusivamente el prototipo de confirmación; se preservan sin cambios conforme a la regla de extensiones ordinarias. Los siguientes usos describen esta landing y no agregan tokens globales.

| Aspecto | Comparación de fuente y alcance |
| --- | --- |
| Paleta | Los ocho colores principales coinciden con el frontmatter de `DESIGN.md`; hover azul `#003b50` y borde `#a9c0c8` también están registrados. El estado activo usa localmente `#002e40`. |
| Tonos auxiliares | Selección `#c8ecec` y scrollbar `#8aabb4` / `#edf3f5` ya aparecen en `confirmation.css`. Ayuda sobre azul `#d1edf2`, línea `#328498` y foco `#8ae0e4` existen en confirmación y en snippets/foco del sidecar, aunque no son primitivos del frontmatter. Esta cobertura documental incompleta es previa a la landing. |
| Familia y jerarquía | Segoe UI continúa la familia registrada; el wordmark conserva Arial. La rampa pública h1 56/48/46/36 px, h2 34/28 px y servicios 22 px adapta la composición institucional permitida. Cuerpo 15–17 px y línea 1.6 amplían el tratamiento compacto de gestión. El descriptor de marca es 6.5 px heredado en escritorio y 6 px en la landing móvil; no se convierte en escala de contenido. |
| Formas y profundidad | Botones 6 px, fotografías de servicio 8 px y banda/panel 12 px coinciden con los radios registrados. Divisiones de 1 px y superficies planas continúan la gramática de confirmación; las filas de servicios no heredan sus formularios ni su densidad. |
| Estados y comportamiento | Botón principal de 48 px, enlaces/navegación de 44 px y foco turquesa de 3 px continúan la intención accesible del prototipo, con offset local de 4 px. Hover sin desplazamiento ni sombra, transiciones de 150 ms, ayuda nativa y movimiento reducido son usos locales; el menú reutiliza `public.js` sin modificarlo. |

No se canonizan ni reparan el descriptor diminuto de marca, los valores auxiliares no enumerados como primitivos ni los estilos públicos heredados fuera de alcance. Tampoco se traslada la jerarquía institucional a gestión.

La revisión independiente tuvo disposición **ship**, sin arreglos materiales, después de inspeccionar las once capturas finales. Este documento conserva el resultado de esa revisión. El estado autenticado de la vista previa era sintético (`auth=1`) y las limitaciones de zoom y autenticación indicadas arriba permanecen vigentes.

## Limpieza e integración

Por solicitud del usuario se eliminaron capturas, resultados temporales, servidores de vista previa y la instalación local de la skill. La aplicación depende de los templates, CSS, JavaScript y fotografías institucionales conservados, y de su backend Django existente. No depende de estas herramientas de revisión. Para iniciar sesión se debe usar el servidor Django habitual; la antigua vista previa del puerto 8768 no implementaba autenticación.

Antes de los commits, en la rama actual, pasaron 58 pruebas de landing, formularios públicos, vistas de estudios, lotes mezclados y paginación. Las fotos institucionales y los assets del visor se conservaron en el equipo; las exclusiones de Git distinguen recursos de la página de capturas y archivos generados.
