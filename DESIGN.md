---
name: "D.O.C. — Confirmación de estudio"
description: "Claridad clínica: prototipo de referencia pendiente de validación."
colors:
  navy: "#004b64"
  teal: "#007d85"
  turquoise: "#00adb5"
  coral: "#f66d68"
  ink: "#163c48"
  muted: "#50666f"
  line: "#d7e3e7"
  pale: "#edf6f6"
  canvas: "#f4f7f8"
  white: "#ffffff"
  navy-hover: "#003b50"
  nav-active: "#09647b"
  nav-hover: "#075b73"
  field-line: "#a9c0c8"
  selected-surface: "#edf8f7"
  result-surface: "#f2f8f8"
  warning-ink: "#715017"
  stage-surface: "#fff2d9"
  warning-surface: "#fff8e9"
  warning-line: "#e9d7b5"
  error-ink: "#8a3633"
  error-surface: "#fff4f2"
  error-line: "#e9bdb7"
  disabled-ink: "#687c84"
  disabled-surface: "#f2f5f6"
typography:
  headline:
    fontFamily: '"Segoe UI", sans-serif'
    fontSize: "28px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-.025em"
  title:
    fontFamily: '"Segoe UI", sans-serif'
    fontSize: "18px"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "-.01em"
  body:
    fontFamily: '"Segoe UI", sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: '"Segoe UI", sans-serif'
    fontSize: "14px"
    fontWeight: 600
  supporting:
    fontFamily: '"Segoe UI", sans-serif'
    fontSize: "13px"
    fontWeight: 400
  caption:
    fontFamily: '"Segoe UI", sans-serif'
    fontSize: "12px"
    fontWeight: 400
rounded:
  control: "6px"
  option: "8px"
  document: "12px"
spacing:
  compact: "8px"
  control-gap: "12px"
  small: "16px"
  medium: "20px"
  section: "24px"
  document: "28px"
components:
  button-primary:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.navy-hover}"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.navy}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
    typography: "{typography.label}"
  button-secondary-hover:
    backgroundColor: "{colors.pale}"
  button-disabled:
    backgroundColor: "{colors.disabled-surface}"
    textColor: "{colors.disabled-ink}"
  field:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
    typography: "{typography.body}"
  navigation-current:
    backgroundColor: "{colors.nav-active}"
    textColor: "{colors.white}"
    rounded: "{rounded.option}"
    padding: "12px 10px"
  stage:
    backgroundColor: "{colors.stage-surface}"
    textColor: "{colors.warning-ink}"
    rounded: "{rounded.control}"
    padding: "7px 10px"
  document:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.document}"
  recipient-selected:
    backgroundColor: "{colors.selected-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.option}"
    padding: "12px"
  result:
    backgroundColor: "{colors.result-surface}"
    textColor: "{colors.ink}"
    padding: "24px 28px"
---

# Design System: D.O.C. — Confirmación de estudio

## Overview

**Creative North Star: "Claridad clínica"**

Este documento registra los tokens del prototipo implementado en la confirmación de estudios, bajo `.confirmation-page`. La aplicación institucional posterior se documenta en `docs/diseno/landing-claridad-clinica.md`, con una jerarquía propia para la landing. El usuario aceptó el trabajo realizado en ambas pantallas; esto no autoriza extender la dirección al resto del sistema. El admin global y las demás páginas conservan su presentación. El material de marca oficial completo sigue pendiente.

La administración cotidiana desde PC determina la densidad: un documento blanco de trabajo, navegación azul D.O.C., jerarquía contenida y separadores finos. La consulta móvil conserva información y acciones legibles. El logo SVG existente mantiene azul, turquesa y coral; no se generaron imágenes ni nuevos activos de marca.

**Key Characteristics:**
- Documento de trabajo claro y plano.
- Navegación azul y selección en turquesa oscuro.
- Sans de sistema legible para el modo Operate.
- Separadores finos, radios moderados y estados con texto visible.
- Reflow móvil sin perder el contexto de revisión.

Fuentes: `static/core/css/confirmation.css`, `static/core/js/confirmation.js`, `apps/estudios/templates/estudios/importacion_detalle.html` y sus includes `confirmation_access.html` y `confirmation_result.html`. El shell se hereda de `templates/core/admin_base.html`; el logo y su wordmark provienen de `doc-isotipo.svg`, `brand.html` y `public.css`. El contrato de esta superficie está en `.impeccable/surfaces/mplates-estudios-importacion-detalle-html-f64976ac.md`.

## Colors

La paleta de este prototipo combina blanco de documento, azul de navegación y un turquesa oscuro legible para interacción. Los valores normativos están en el frontmatter.

### Primary
- **Azul D.O.C.** (`navy`): rail, botones principales y enlaces de acción; `navy-hover` oscurece botones.
- **Turquesa de interacción** (`teal`): selección, radios, iconos funcionales, caret y foco. Conserva el parentesco con el turquesa del logo.

### Secondary
- **Turquesa de marca** (`turquoise`): isotipo y wordmark existentes.
- **Coral de marca** (`coral`): centro del isotipo. En esta superficie no se usa como fondo de acción.

### Neutral
- **Tinta clínica** (`ink`) y **texto secundario** (`muted`): datos, ayudas y metadatos.
- **Lienzo** (`canvas`) y **documento** (`white`): separación entre entorno y trabajo.
- **Línea** (`line`) y **borde de campo** (`field-line`): divisiones y controles.
- **Superficie suave** (`pale`), **selección** (`selected-surface`) y **resultado** (`result-surface`): estados y zonas con tonalidad discreta.
- `nav-active` y `nav-hover` distinguen el módulo actual y la interacción en el rail.
- `warning-*`, `stage-surface` y `error-*` acompañan estados explícitos; `disabled-*` mantiene legibles las acciones deshabilitadas.

**The Visible State Rule.** En este prototipo, el color de selección acompaña un radio y una identidad visible; los avisos siempre incluyen texto.

## Typography

**Headline / Body Font:** Segoe UI, con fallback sans-serif. Es la sans de sistema implementada para Operate; no se ha elegido una tipografía institucional nueva. El wordmark heredado conserva Arial y su tratamiento existente.

### Hierarchy
- **Headline:** título de página; la variante móvil baja a 26px.
- **Title:** encabezados de sección. El encabezado del resultado usa 16px.
- **Body:** texto base y campos. Ayudas y hechos usan 14px; la introducción usa 15px.
- **Label:** etiquetas y acciones con peso 600.
- **Supporting / Caption:** datos auxiliares y estados de paginación. Los totales usan cifras tabulares.
- Datos destacados del contexto: 16px, peso 650 y línea 1.4.

Las ayudas tienen un ancho máximo de 65ch; la introducción, 68ch. Se prioriza la lectura de nombres y datos largos mediante reflow.

## Layout

Esta composición pertenece a la confirmación; no es una plantilla obligatoria para otras páginas. En escritorio, el shell reserva un rail de 220px y contenido fluido. El área principal mide `min(1220px, calc(100% - 64px))`, con 28px arriba y 40px abajo.

El documento reúne contexto, revisión y consecuencia. Su banda de contexto usa tres columnas (1.2fr / 1fr / 1fr), con 24px de separación y 22px × 28px de padding. La revisión usa dos zonas (1fr / 1.08fr), 28px de separación y padding; el destinatario se separa con una línea vertical. La lista de destinatarios tiene scroll propio a partir de 238px de alto.

A 1150px el resultado pasa a columna y el título permite reflow. A 900px el rail cede su lugar a navegación nativa plegable, la revisión pasa a una columna y los márgenes laterales son 20px. A 600px el contexto se apila, los márgenes son 16px, el documento usa 20px de padding lateral y la acción principal ocupa todo el ancho. Las grillas permiten encoger contenido con `minmax(0, 1fr)`; nombres y correos pueden partirse.

## Elevation & Depth

El documento, los campos, las opciones y los botones no llevan sombra. Su separación depende de fondos y bordes finos. El único volumen propio de este prototipo es el diálogo nativo de paciente existente: sombra `0 16px 48px #003b5033` y backdrop `#163c4870`.

**The Flat Work Surface Rule.** Dentro de la confirmación, la sombra distingue el diálogo superpuesto; la revisión permanece plana.

## Shapes

Los controles tienen esquinas discretas (`control`), las opciones y avisos usan `option` y el documento y diálogo usan `document`. Los bordes estructurales son de 1px. La banda de resultado conserva las dos esquinas inferiores del documento.

Los iconos usan el SVG local existente, con stroke de 1.7 y extremos redondeados, acompañados de texto. Las secciones usan iconos de 24px; acciones y metadatos reducen su tamaño según el contexto. El enlace público de esta pantalla sobreescribe el glyph heredado con el SVG de flecha girado; otras páginas conservan su implementación.

## Components

### Buttons
Botón azul con texto blanco, mínimo de 46px, línea 1.4 y sin desplazamiento al hover. El secundario usa blanco, borde de campo y texto azul; su hover usa `pale`. La paginación baja a 44px, con 9px × 12px y texto de 13px. Deshabilitado conserva opacidad completa y comunica el estado con tono y cursor.

### Inputs / Fields
Campos blancos de mínimo 46px, texto de 16px y borde de campo. El foco cambia el borde a turquesa oscuro y elimina sombras. Los errores usan borde y ayuda en `error-ink`. Los placeholders permanecen opacos y legibles.

### Navigation
Rail azul con opciones de mínimo 70px, icono, título y ayuda. La opción actual combina fondo, borde y `aria-current`. A 900px aparece un `details/summary` con enlaces de 48px; Escape cierra el menú y devuelve el foco al summary.

### Chips
La etiqueta de estado es informativa: texto de 12px y peso 600 sobre `stage-surface`. Expresa el estado real de la importación y no actúa como filtro.

### Cards / Containers
Un documento blanco con borde fino contiene la revisión. Los avisos usan 18px × 22px, radio de opción y mensajes semánticos `status` o `alert`. Las correcciones usan un disclosure nativo de mínimo 52px y un SVG plus que rota al abrir.

### Recipient Selection
Opciones de mínimo 74px, radio de 18px, identidad de 14px y metadatos de 13px. Hover aclara el fondo; la selección combina borde turquesa y `selected-surface`. El foco dentro de la opción dibuja un outline de 3px con offset de 1px. La selección se anuncia con `aria-live="polite"`.

### Confirmation Result
La consecuencia y el destinatario se actualizan desde la selección real. Sin derivante, el texto y el botón indican borrador; con derivante, explican el intento de publicación sujeto a verificaciones. La presentación no inventa una publicación exitosa ni cambia el formulario o la validación del servidor.

El foco general usa outline turquesa de 3px con offset de 3px; sobre navegación azul usa un tono claro. Las transiciones de selección duran 120ms, el disclosure 140ms; se respetan las preferencias de movimiento reducido.

## Do's and Don'ts

### Do:
- **Do** limitar estos tokens y patrones al prototipo de confirmación hasta su validación.
- **Do** conservar el logo SVG y los colores existentes de D.O.C.
- **Do** mantener campos de 16px, botones de al menos 44px y foco visible.
- **Do** expresar selección y consecuencias con datos reales y texto legible.
- **Do** permitir reflow de nombres, correos y acciones en móvil.

### Don't:
- **Don't** interpretar esta extracción como aprobación de una identidad global.
- **Don't** convertir la composición de confirmación en una obligación para todas las páginas.
- **Don't** afirmar publicación exitosa antes de la respuesta del servidor.
- **Don't** trasladar el glyph heredado del enlace público a los iconos del prototipo.

No canonizado ni reparado por esta documentación: estilos heredados fuera de alcance y el glyph del enlace público de otras páginas. La revisión del prototipo resolvió el único hallazgo solicitado mediante su override SVG, sin cambiar el comportamiento global. El detector no resolvió el enlace estático de Django; sus tokens se contrastaron directamente con el CSS.
