# Referencia D.O.C. · Confirmación de estudio

Estado: prototipo implementado y trabajo aceptado por el usuario; extenderlo a otras pantallas requiere una nueva instrucción. Dirección: **claridad clínica**. Fecha: 5 de octubre de 2026.

La pantalla conserva el logo, el azul D.O.C. y el turquesa; el coral pertenece al isotipo. La tipografía de sistema evita nuevas dependencias. Un documento de trabajo reúne contexto, revisión, destinatario y consecuencia de la confirmación.

## Comportamiento visual

- Paciente, tipo, fecha y acceso se reconocen al comienzo. Las correcciones y el odontólogo elegido actualizan ese contexto.
- Los datos detectados se pueden corregir mediante una sección plegable. Los errores la abren y conservan los campos y errores de Django.
- El selector usa radios nativos y filas con dos columnas reales: control e identidad. Mantiene búsqueda, paginación y selección remota existentes. Incluye recuperación cuando no hay coincidencias.
- Sin derivante: «Guardar como borrador», explicando que el estudio aún no estará disponible para consulta.
- Con derivante: «Confirmar y publicar», identificando al destinatario y aclarando que la publicación depende de las verificaciones. No se simula éxito; el estado final aparece en la ficha tras la respuesta del servidor existente.
- En móvil, la navegación se pliega sin superponer el formulario; el documento se reorganiza en una columna. Campos de 16px y botones de al menos 44px.
- Se conservan identificación de paciente, validación por DNI, revisión de estudios distintos y bloqueo de carpetas con identidades mezcladas.

## Alcance técnico

Template: `apps/estudios/templates/estudios/importacion_detalle.html`. Componentes específicos: `includes/confirmation_access.html` y `includes/confirmation_result.html`. CSS y resumen de presentación: `static/core/css/confirmation.css` y `static/core/js/confirmation.js`.

La base de administración incorpora tres bloques vacíos para cargar estilos, clase de pantalla y navegación móvil únicamente desde esta ruta, además de un bloque que conserva el icono heredado por defecto y permite reemplazarlo por SVG en el prototipo. El script de análisis cambia una frase técnica por un mensaje para el personal del centro. Los selectores compartidos, rutas, campos enviados, CSRF, formularios, modelos, permisos y lógica de publicación se conservan.

## Verificación

- Navegador: 1440, 1024, 768, 390 y 320px; sin desbordamiento horizontal, controles visibles sin etiquetas ausentes ni referencias ARIA rotas, botones y resúmenes de al menos 44px.
- Selección y borrador, búsqueda vacía, fallo de búsqueda, paginación conservando el destinatario, corrección de paciente/tipo/fecha y POST nativo con campos originales comprobados con datos ficticios.
- Estados: sin paciente identificado, error de formulario, carpeta mezclada, revisión obligatoria, odontólogo previamente seleccionado, selección no disponible y análisis pendiente.
- 21 pruebas Django pertinentes aprobadas: identificación por DNI, creación de ficha sin cuenta, escape de nombres, selectores de ambas variantes, apertura de errores y reglas de carpetas mezcladas/revisión.
- En una ejecución más amplia, cuatro pruebas de transferencias requieren bloqueos MySQL y fallan bajo SQLite. No se modificó esa infraestructura. El prototipo no prueba transferencias reales ni publicación en producción.
- Detector ejecutado una vez sobre los archivos modificados: sin hallazgos. No puede resolver las etiquetas Django de las hojas enlazadas; el CSS se incluyó como objetivo independiente y el render se comprobó en navegador.
- Antes de los commits, en la rama actual: 58 pruebas aprobadas de landing, formularios públicos, vistas de estudios, lotes mezclados y paginación. Se actualizaron dos pruebas de presentación a los textos y selector del prototipo; se mantuvieron las comprobaciones de borrador, publicación, permisos y bloqueo de carpetas mezcladas.

Las capturas y mediciones fueron evidencia temporal y se eliminaron durante la limpieza solicitada por el usuario. La vista previa utilizó templates reales, datos ficticios y un receptor POST que no guardaba información; no sustituyó un entorno integrado con autenticación, base de datos y almacenamiento.

## Integración y revisión

La pantalla se integra en la ruta existente de detalle de importación del servidor Django habitual. Los servidores de vista previa de los puertos 8767 y 8768 se retiraron; nunca implementaron autenticación ni persistencia reales.

El código necesario está en los templates y assets indicados arriba. No depende de la skill, sus ejecutables, capturas ni scripts temporales. El aviso «datos ficticios» pertenecía al servidor de vista previa; no forma parte del producto.

La revisión independiente indicó una corrección: reemplazar el icono Unicode heredado por SVG solo en el prototipo. Tras aplicarla y recapturar las mismas vistas, el revisor la calificó como resuelta (`disposition: ship`, alcance del dictamen: esa corrección). Este documento conserva el resultado; los tokens se documentan en `DESIGN.md` y `.impeccable/design.json`. La aceptación de estas pantallas no autoriza extender el diseño a otras vistas.
