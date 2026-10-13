# Auditoría técnica de interfaz D.O.C.

Fecha: 5 de octubre de 2026. Skill: Impeccable, comando `audit`. No se modificó código de la aplicación.

## Veredicto de integridad de implementación

**No pasa la consistencia técnica del sistema.** La identidad D.O.C. es reconocible y las superficies responden al producto odontológico. Sin embargo, hay reglas duplicadas que sobrescriben la estructura del explorador, estilos inline que neutralizan adaptaciones responsive y componentes compartidos con comportamientos de foco incompletos. No hace falta sustituir la identidad para corregir estos problemas.

El detector produjo **17 alertas primarias**. Se contrastaron con el código y la interfaz renderizada; no equivalen a 17 defectos. El análisis de templates Django no resolvió cuatro referencias de estilos con `{% static %}`, por lo que se comprobó el CSS servido en navegador. La jerarquía plana atribuida al visor es un falso positivo: sus títulos renderizados miden 33/26 px. Los avisos sobre Arial/Inter, bordes laterales y padding de iconos no demuestran defectos técnicos y se excluyeron de los hallazgos. El icono de aviso blanco sobre amarillo es decorativo (`aria-hidden="true"`); su contraste 1,90:1 no se contabilizó como fallo de texto. Sí se verificaron contraste de texto y tipografía funcional pequeña.

## Resultado

| Dimensión | Puntuación | Hallazgo principal |
|---|---:|---|
| Accesibilidad | 2/4 | Cuatro filtros sin etiquetas asociadas y texto con contraste insuficiente. |
| Rendimiento | 3/4 | Imagen principal de 1,47 MB sin variantes responsive; visor con carga diferida. |
| Responsive | 2/4 | Administración recorta acciones a 390 px; dos pantallas desbordan a 320 px. |
| Theming | 2/4 | Tokens útiles, pero paletas y superficies repetidas fuera de ellos. |
| Integridad de implementación | 2/4 | Cascada contradictoria y estructura nativa de carpetas incompleta. |
| **Total** | **11/20** | **Aceptable: requiere trabajo significativo.** |

**11 hallazgos agrupados: P0: 0; P1: 4; P2: 7; P3: 0.** Priorizar etiquetas, contraste y reflow antes de publicación. La puntuación es una evaluación técnica del alcance inspeccionado, no una certificación WCAG.

## Alcance y evidencia

- Inspección estática de templates públicos, autenticación, usuarios, pacientes, estudios; CSS y JavaScript compartidos; visor y sus assets compilados.
- Renderizado de templates y assets reales con datos sintéticos en servidor loopback, configuración Django de pruebas y sin consultas a datos reales. El servidor fue detenido al terminar.
- Nueve pantallas: portada, login, recuperación, registro profesional, portal profesional, portal del paciente, lista administrativa de odontólogos, detalle de estudio y visor. Chromium headless; viewports de **1365 × 900, 390 × 900 y 320 × 900**. Capturas de escritorio y 390 px; mediciones DOM para las tres anchuras.
- Interacción adicional a 390 × 844 con `hasTouch`, viewport móvil y eventos táctiles sintetizados por CDP: rotación STL y desplazamiento DICOM alteraron la imagen; cancelar el gesto permitió restablecer la vista; cerrar eliminó el canvas. Flecha derecha avanzó DICOM a **2 / 16**. Menú público: Escape cerró y devolvió el foco al botón.
- No hubo errores JavaScript no capturados en las pantallas revisadas ni en esos ejercicios del visor.
- No se verificaron dispositivos físicos, Firefox/Safari, zoom de texto al 200 %, lectura con tecnología asistiva, carga clínica de gran tamaño, red de producción ni Core Web Vitals. Los endpoints de búsquedas remotas no forman parte del servidor sintético; sus mensajes de error no se reportaron como defectos del producto. Los estados POST y otros estados condicionales se revisaron en código cuando correspondía.
- Evidencia temporal: mediciones DOM, interacciones, detector y capturas usadas durante la auditoría. Por solicitud del usuario, esos archivos y los scripts de reproducción se eliminaron en la limpieza posterior; este informe conserva los resultados y sus límites.

## Hallazgos P1 — corregir antes de publicar

### 1. Filtros profesionales sin etiquetas programáticas

- **Ubicación:** [dashboard_odontologo.html:87](../../apps/usuarios/templates/usuarios/dashboard_odontologo.html:87), campos en líneas 88, 94, 104 y 110.
- **Categoría:** Accesibilidad.
- **Evidencia:** `q`, `tipo`, `fecha_desde` y `fecha_hasta` tienen etiquetas visuales separadas sin `for`, controles sin `id` y sin nombre ARIA. El DOM confirmó `labels.length === 0` para los cuatro en todas las anchuras. El placeholder de búsqueda no sustituye las etiquetas de todos los controles.
- **Impacto:** Un lector de pantalla no puede asociar con fiabilidad el nombre visible de cada filtro; pulsar la etiqueta tampoco enfoca el control.
- **Estándar:** WCAG 1.3.1, Información y relaciones; 4.1.2, Nombre, función y valor.
- **Recomendación:** Añadir IDs únicos y `for` en cada etiqueta; conservar nombres visibles y tipos nativos.
- **Comando:** `$impeccable harden`.

### 2. Contraste insuficiente en información funcional

- **Ubicación:** [admin.css:34](../../static/core/css/admin.css:34), [visor.css:4](../../frontend/visor/visor.css:4), [importacion_crear.html:19](../../apps/estudios/templates/estudios/importacion_crear.html:19).
- **Categoría:** Accesibilidad / Theming.
- **Evidencia:** Subtítulos de navegación administrativa: `#819096` sobre blanco, **3,30:1**. Aviso orientativo del visor: `#667f86` sobre `#f2f7f7`, **3,93:1**. Texto condicional «ATENCIÓN REQUERIDA»: `#b27b00` sobre `#fffcf5`, **3,58:1**; este último se comprobó por código y cálculo, no en la fixture renderizada. Son textos pequeños, requieren 4,5:1.
- **Impacto:** Se dificulta leer contexto de navegación y avisos sobre el estudio, especialmente con baja visión.
- **Estándar:** WCAG 1.4.3, Contraste mínimo.
- **Recomendación:** Crear tokens para texto secundario y advertencias que alcancen 4,5:1 sobre sus superficies; revisar sus usos renderizados.
- **Comando:** `$impeccable colorize`.

### 3. Administración móvil recorta acciones y superpone navegación

- **Ubicación:** [admin.css:227](../../static/core/css/admin.css:227), línea 242; [admin.css:502](../../static/core/css/admin.css:502), línea 661; [odontologo_lista.html:12](../../apps/usuarios/templates/usuarios/odontologo_lista.html:12).
- **Categoría:** Responsive / Accesibilidad.
- **Evidencia:** A menos de 420 px el sidebar reserva 145 px, pero sus enlaces exigen `min-width:174px` más padding del contenedor. En detalle a 390 px una tarjeta de archivo ocupa x=207…427; «Ver en 3D» y «Marcar incorrecto» llegan a x=414, dentro de una sección con `overflow:hidden`. Por eso `scrollWidth === 390` no significa que todo sea visible. En lista de odontólogos a 320 px, el grupo contador/«Ver» alcanza **362 px** y desborda.
- **Impacto:** La navegación invade el espacio de trabajo y las acciones de archivos quedan parcialmente ocultas en teléfono.
- **Estándar:** WCAG 1.4.10, Reflow; recortes además de scroll horizontal.
- **Recomendación:** Convertir el sidebar en navegación plegable o superior en móvil; eliminar mínimos contradictorios; permitir que tarjetas y grupos de acciones se apilen dentro del ancho disponible. Revisar con archivos presentes y lista vacía.
- **Comando:** `$impeccable adapt`.

### 4. Tarjetas profesionales desbordan a 320 px

- **Ubicación:** [dashboard_odontologo.html:139](../../apps/usuarios/templates/usuarios/dashboard_odontologo.html:139), [public.css:431](../../static/core/css/public.css:431).
- **Categoría:** Responsive / Accesibilidad.
- **Evidencia:** El estilo inline `repeat(auto-fill,minmax(340px,1fr))` gana a la regla móvil que intenta establecer una columna. Con viewport de 320 px el contenedor tiene 280 px, la tarjeta mide 340 px y el documento alcanza **360 px**.
- **Impacto:** Hay que desplazarse horizontalmente para leer y operar las tarjetas del consultorio.
- **Estándar:** WCAG 1.4.10, Reflow.
- **Recomendación:** Mover la definición de columnas a CSS, usar una columna móvil y mínimos limitados por el ancho disponible, sin añadir otro parche inline o `!important`.
- **Comando:** `$impeccable adapt`.

## Hallazgos P2 — siguiente pasada

### 5. El menú de vistas pierde el foco y no responde a Escape

- **Ubicación:** [file_view.js:42](../../static/core/js/file_view.js:42), también líneas 20–38.
- **Categoría:** Accesibilidad / Integridad.
- **Evidencia:** Tras seleccionar «Detalles», se oculta el botón enfocado y `document.activeElement` pasa a `BODY`. Tras volver a abrir y pulsar Escape, `aria-expanded` permanece `true`. La elección se expresa únicamente con `.is-active`, sin estado accesible.
- **Impacto:** El usuario de teclado pierde su posición al cambiar de vista y no tiene un cierre consistente con el menú público.
- **Estándar:** Riesgo en WCAG 2.4.3, Orden del foco; 4.1.2 para estado de selección. No se constató una trampa de teclado.
- **Recomendación:** Usar un patrón de disclosure con botones ordinarios, `aria-controls`, estado de selección y devolución de foco al disparador al cerrar; añadir Escape. Si se adopta un menú ARIA, implementar también su navegación completa.
- **Comando:** `$impeccable harden`.

### 6. La vista «Detalles» declara columnas contradictorias

- **Ubicación:** [admin.css:531](../../static/core/css/admin.css:531), sobrescrito por [admin.css:644](../../static/core/css/admin.css:644).
- **Categoría:** Integridad / Responsive.
- **Evidencia:** La primera regla define cuatro columnas `2fr .75fr 1fr auto`; la segunda reemplaza la misma propiedad por tres `2fr 1fr 1fr`. En navegador se obtuvieron **461px 230.5px 230.5px** para una fila con cinco hijos en administración, incluidos acciones y corrección.
- **Impacto:** Las acciones se colocan por auto-placement en otra fila y la vista no respeta la estructura declarada originalmente; futuras modificaciones dependen del orden del CSS.
- **Estándar:** Consistencia de implementación, sin infracción WCAG independiente demostrada.
- **Recomendación:** Consolidar un único layout por modo de vista y asignar explícitamente las áreas para nombre, tamaño, formato, acciones y corrección, con variante móvil.
- **Comando:** `$impeccable layout`.

### 7. La carpeta raíz genera un summary nativo «Details»

- **Ubicación:** [_folder_explorer_node.html:1](../../apps/estudios/templates/estudios/_folder_explorer_node.html:1).
- **Categoría:** Integridad / Accesibilidad.
- **Evidencia:** La raíz se envuelve en `<details open>`, pero omite `<summary>` y usa un banner `<div>`. Chromium incorpora el control predeterminado «Details», visible por encima de «Carpeta principal» en la captura móvil.
- **Impacto:** Aparece un control extra, en inglés, que permite colapsar todos los archivos sin un nombre que explique su alcance.
- **Estándar:** Semántica nativa y consistencia del idioma de controles; no se atribuye una infracción normativa automática.
- **Recomendación:** Usar un contenedor ordinario para la raíz siempre visible; reservar `details/summary` para subcarpetas, o dar a la raíz un summary explícito en español.
- **Comando:** `$impeccable harden`.

### 8. Tipografía funcional excesivamente pequeña

- **Ubicación:** [admin.css:26](../../static/core/css/admin.css:26), líneas 34, 85, 186, 497 y 515; [dashboard_odontologo.html:169](../../apps/usuarios/templates/usuarios/dashboard_odontologo.html:169).
- **Categoría:** Integridad / Accesibilidad.
- **Evidencia:** Subtítulos de navegación: **10,4 px**; formato de archivo profesional: **10,88 px**; categorías del resumen: **10,56 px**. El CSS declara etiquetas de navegación móvil a **8,64 px** y cabeceras de archivo a **9,76 px**. Se excluye la leyenda del logotipo del conteo de texto funcional.
- **Impacto:** Formatos, categorías y contexto de navegación requieren esfuerzo adicional de lectura.
- **Estándar:** Criterio de legibilidad del detector; WCAG no establece un mínimo universal de píxeles. No se comprobó incumplimiento de 1.4.4.
- **Recomendación:** Establecer una escala para etiquetas y metadatos de 12–14 px como referencia, evitando reducir texto para sostener el sidebar móvil.
- **Comando:** `$impeccable typeset`.

### 9. Controles táctiles del visor por debajo de 44 px

- **Ubicación:** [visor.css:5](../../frontend/visor/visor.css:5), variante móvil en línea 7.
- **Categoría:** Responsive.
- **Evidencia:** A 390 px, botones de toolbar de **33 px** de alto; zoom + de **35 × 33 px** y zoom − de **31,64 × 33 px**. «Actualizar opciones» mide 28 px de alto.
- **Impacto:** Hay menos margen para acertar al tocar zoom, rotación y cierre en un visor ya denso.
- **Estándar:** Objetivo 44 × 44 del playbook y WCAG 2.5.5 AAA. No se presenta como fallo AA de 2.5.8: estos botones superan su mínimo de 24 px.
- **Recomendación:** Aumentar área activa y separación en móvil, manteniendo una zona amplia para la imagen y los gestos.
- **Comando:** `$impeccable adapt`.

### 10. Imagen principal sin tamaños de descarga adaptados

- **Ubicación:** [landing.html:19](../../templates/core/landing.html:19), asset `static/core/images/doc-equipo-original.jpg`.
- **Categoría:** Rendimiento.
- **Evidencia:** JPEG de **1.468.718 bytes**, dimensiones declaradas **1754 × 2480**, servido con un único `src` sin `srcset` ni `sizes`; móvil descarga el mismo archivo. El encuadre se resuelve ampliando y recortando mediante CSS. Tiene `fetchpriority="high"`, por lo que compite tempranamente por ancho de banda.
- **Impacto:** La portada transfiere más datos de los necesarios en redes móviles. No se midió un LCP de producción ni se afirma que incumpla Core Web Vitals.
- **Recomendación:** Crear variantes del encuadre institucional, optimizar formato/calidad y ofrecer `picture/srcset/sizes`; conservar prioridad alta si sigue siendo la imagen LCP. Mantener el original como fuente.
- **Comando:** `$impeccable optimize`.

### 11. Tokens fragmentados entre superficies

- **Ubicación:** [public.css:3](../../static/core/css/public.css:3), [visor.css:1](../../frontend/visor/visor.css:1), [dashboard_odontologo.html:29](../../apps/usuarios/templates/usuarios/dashboard_odontologo.html:29).
- **Categoría:** Theming / Integridad.
- **Evidencia:** Público define `--teal:#007d85`, visor redefine `--teal:#008994`; portales usan además `#007788`. Superficies, estados, bordes y tipografía se repiten en estilos inline y hexadecimales; el CSS administrativo contiene hexadecimales en 90 líneas. El visor emplea una fuente distinta de la base pública. El contraste fallido del hallazgo 2 también queda fuera de tokens semánticos compartidos.
- **Impacto:** Ajustar accesibilidad o identidad requiere localizar múltiples valores independientes, con riesgo de nuevas divergencias.
- **Estándar:** Consistencia y mantenibilidad. No se penaliza la ausencia de modo oscuro: no se encontró una promesa ni un selector de ese modo.
- **Recomendación:** Definir tokens semánticos compartidos para texto, superficies y estados; mantener tokens específicos del canvas oscuro donde corresponda. Extraer estilos repetidos de los templates y documentar las diferencias intencionales.
- **Comando:** `$impeccable extract` y `$impeccable document`.

## Patrones y prácticas que conviene mantener

Los problemas principales vienen de mínimos de anchura incompatibles con el espacio disponible, estilos inline y reglas añadidas al final del CSS. Las adaptaciones del filtro profesional ya usan `!important`, mientras la grilla de tarjetas mantiene su mínimo inline. Conviene consolidar cada componente en vez de sumar más excepciones.

Hay buenas bases: `lang="es-AR"`, viewport correcto, landmarks, enlaces para saltar contenido, foco visible, `aria-current`, estados de carga anunciados, formularios nativos y etiquetas correctamente vinculadas en autenticación. El menú público cierra con Escape y restaura foco. El registro conserva las relaciones de ayuda generadas por Django; no se detectaron referencias ARIA rotas en las nueve fixtures.

La portada reserva dimensiones de imágenes y usa lazy loading en imágenes de servicios. El visor comienza con un entrypoint de **8.398 bytes** y carga módulos STL/PLY y DICOM bajo demanda. El chunk DICOM de 3.571.842 bytes y el de modelos de 554.571 bytes merecen seguimiento en perfiles reales, pero no se declararon dependencias innecesarias sin prueba. Hay parser en worker, cancelación, límites, render por cambios en modelos y liberación explícita de geometrías, renderer y listeners. Las interacciones sintéticas verificaron cierre de canvas y navegación DICOM. La hoja pública respeta reduced motion; no se encontró que desactivar sus transiciones decorativas destruyera información de estado.

## Orden recomendado

1. **P1 — `$impeccable harden`:** Asociar los cuatro filtros con sus etiquetas.
2. **P1 — `$impeccable colorize`:** Corregir los tres pares de contraste de texto señalados.
3. **P1/P2 — `$impeccable adapt`:** Replantear sidebar móvil, quitar mínimos que recortan archivos/tarjetas y ampliar controles del visor.
4. **P2 — `$impeccable harden`:** Resolver foco/estado del menú de vistas y semántica de carpeta raíz.
5. **P2 — `$impeccable layout`:** Consolidar columnas y áreas del explorador.
6. **P2 — `$impeccable typeset`:** Elevar tamaños de etiquetas y metadatos funcionales.
7. **P2 — `$impeccable optimize`:** Generar variantes de la imagen principal.
8. **P2 — `$impeccable extract` / `$impeccable document`:** Unificar tokens y registrar decisiones. `$impeccable init` puede capturar el contexto de producto que todavía no está documentado.
9. **Cierre — `$impeccable polish`:** Verificar el resultado de las correcciones en escritorio y móvil.

Podés pedir que ejecute estas correcciones una por una, juntas o en el orden que prefieras. Después, volver a ejecutar `$impeccable audit` permitirá comparar la puntuación y verificar los hallazgos resueltos.
