# D.O.C. — contexto del producto

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Confirmado por el usuario el 5 de octubre de 2026: la experiencia principal es la administración del centro desde PC. Odontólogos y pacientes consultan estudios también desde teléfonos.

## Product Purpose

Gestionar, publicar y consultar estudios odontológicos de D.O.C. La propuesta visual debe facilitar el trabajo cotidiano del centro y la consulta de estudios, con una estética profesional, moderna, limpia, seria y confiable.

## Capabilities and Constraints

El repositorio implementa un monolito Django con templates, CSS y JavaScript; el visor usa módulos compilados con Vite, Three.js y Cornerstone. La revisión de código documenta carga de carpetas, detección de datos, confirmación manual, fichas de pacientes, cuentas de odontólogos, estados de publicación, permisos de consulta y visor de archivos compatibles. Estas capacidades describen la implementación existente; no autorizan cambios de negocio.

Los permisos y los estados de cuenta son parte de la lógica existente. La identidad visual propuesta no debe inventar nuevas capacidades, métricas ni resultados de publicación. Las confirmaciones y los mensajes de éxito deben reflejar respuestas reales del servidor.

## Brand Commitments

El usuario solicita redefinir la identidad de la interfaz sin perder la identidad de marca y evitar la apariencia de una plantilla SaaS genérica. Se preservan el nombre D.O.C. y su logotipo.

No hay una tipografía obligatoria, según confirmó el usuario. El repositorio usa azul `#004B64`, turquesa `#00ADB5` y coral `#F66D68` en su isotipo; son evidencia del sistema actual, no una aprobación de una nueva paleta. Está pendiente recibir el material de marketing del cliente antes de fijar colores, tratamientos gráficos y fotografías de la propuesta final.

Para el prototipo de confirmación, el usuario pidió expresamente mantener el logo y estos colores, aplicando la dirección «claridad clínica». Esta elección autoriza la pantalla de referencia; la extensión al resto del sistema depende de su validación.

## Evidence on Hand

- Logo e imágenes institucionales en `static/core/images/`.
- Auditoría técnica del 5 de octubre: `docs/auditorias/2026-10-05-impeccable.md`.
- Critique aportado por el usuario: evaluación de administración, especialmente carga y confirmación de estudios, 23/40; conserva la marca y señala problemas de selección, reflow y claridad de consecuencias.
- Resultados históricos de auditoría y verificación resumidos en los documentos del proyecto. Las capturas y herramientas temporales se eliminaron durante la limpieza solicitada por el usuario.

## Product Principles

- La administración diaria desde PC guía la densidad y la jerarquía.
- La consulta móvil debe conservar nombres, fechas, estados y acciones legibles.
- El sistema debe comunicar confianza mediante claridad y consistencia.
- La marca D.O.C. se conserva; la expresión visual de la interfaz puede redefinirse.
- La información clínica, los destinatarios y las consecuencias de cada acción tienen prioridad sobre decoración.

## Open Decisions

- Material de marketing pendiente de adjuntar y revisar.
- «Claridad clínica» se implementa como prototipo en la confirmación de estudios. Su validación visual y la extensión al sistema están pendientes.
- Se autorizó e implementó también la landing como primera aplicación pública: servicios y contacto prioritarios. Los cambios realizados fueron aceptados por el usuario; no se autoriza extenderlos a más pantallas ni modificar framework o lógica de negocio.
