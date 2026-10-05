---
version: 1
slug: "mplates-estudios-importacion-detalle-html-f64976ac"
primary_target: "apps/estudios/templates/estudios/importacion_detalle.html"
related_targets: ["static/core/css/confirmation.css","static/core/js/confirmation.js"]
---

# Confirmación de estudio

Scope: solo importacion_detalle y sus componentes específicos. Mode: Operate. Administración diaria en PC; consulta y revisión en móvil. Dirección fijada por el usuario: claridad clínica, logo y colores D.O.C. Sin cambios de negocio, permisos, modelos ni backend. Este prototipo requiere validación del usuario antes de extenderse.

## Direction contract

THESIS: Revisar paciente, estudio y destinatario antes de confirmar. Evitar títulos promocionales y tarjetas anidadas.

OWN-WORLD: Azul D.O.C. en la navegación, blanco en el documento de trabajo, turquesa oscuro en selección y coral solo en el logo. Una sans de sistema legible, separadores finos, radios moderados.

STORY: Ver datos detectados; corregir solo si hace falta; seleccionar un odontólogo o dejar sin asignar; comprender borrador o publicación sujeta a verificaciones; enviar el formulario existente.

FIRST VIEWPORT: Encabezado compacto y navegación a la izquierda en PC. Título de 28px, contexto Paciente · Estudio · Acceso en una banda y dos zonas para revisión y derivante. Resultado y acción al final en flujo. Móvil: menú nativo plegable, una columna, texto de 16px en campos y botones de al menos 44px.

FORM: Claridad clínica editorial, dirección elegida explícitamente por el usuario desde shape; seed previo ceada702, candidato 3, sin catálogo externo. Implementación directa del prototipo real, sin comp ni cambio de preferencia de construcción. Firma: contexto y consecuencia actualizados por la selección real, sin modificar valores ni POST.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Open: marketing del cliente pendiente; esta pantalla no autoriza cambios en otras rutas.
