# D.O.C. — propuesta de dirección visual

Estado: propuesta preliminar, 5 de octubre de 2026. Pendiente contrastar con el material de marketing del cliente. No constituye un sistema aprobado ni una implementación.

## Dirección recomendada: claridad clínica

Un sistema de gestión de estudios que transmite la precisión y la cercanía de D.O.C. mediante información bien ordenada, decisiones explícitas y una marca reconocible. La referencia visual es la claridad editorial de la comunicación clínica institucional: jerarquía breve, datos alineados y separación precisa entre identidad, contenido y estado. Esa referencia aporta tipografía, paleta, densidad y una continuidad visual; la navegación y los controles siguen siendo los habituales de una aplicación web.

La experiencia principal es la administración cotidiana del centro en PC, confirmada por el usuario. La consulta de odontólogos y pacientes debe resultar cómoda desde teléfonos. Esta diferencia guía la densidad: administración permite comparar registros; consulta favorece identificar un estudio y abrirlo.

La marca debe sentirse por el azul, el isotipo, el tono de atención y el cuidado de los datos. El carácter específico del producto aparece al mostrar quién es el paciente, qué estudio se está gestionando y quién puede consultarlo. No depende de un dashboard de indicadores ni de decoración tecnológica.

## Evidencia y alcance de revisión

Se inventariaron los 43 templates del frontend propio, incluidos componentes, correo de recuperación y bases. Se revisaron las familias de pantallas, CSS público/administrativo/visor y los scripts de carga, selección, acceso y explorador; se reutilizó la evidencia visual de la auditoría de nueve pantallas en escritorio y móvil. Esto cubre el código del frontend completo y muestras de su renderizado; no significa haber ejecutado todos los estados de cada pantalla.

El fingerprint SHA256 de `templates/core/admin_base.html` coincide con el critique adjunto: `40840d747834bced26ee07682e6f40802ae3d42874e716ebc9d7ff269b31e36d`. Se distingue lo observado de lo propuesto y de las limitaciones de pruebas. El critique es evidencia para esta propuesta, no una autorización independiente para modificar la aplicación.

Fuentes: [auditoría técnica](../../docs/auditorias/2026-10-05-impeccable.md), critique adjunto por el usuario, templates y evidencia temporal resumida en la auditoría. Las capturas se eliminaron durante la limpieza posterior solicitada por el usuario.

## Qué preservar y qué redefinir

| Aspecto | Decisión propuesta | Razón |
|---|---|---|
| Nombre e isotipo D.O.C. | Preservarlos; contrastar variantes con archivos del cliente. | Son la identidad de marca, no un componente a reinventar. |
| Azul, turquesa y coral | Conservar su reconocimiento; distribuir sus usos por función. | La marca continúa siendo reconocible con menor saturación decorativa. |
| Fotografías institucionales | Mantenerlas en la web pública y revisarlas con el material de marketing. | Dan evidencia concreta del centro y su equipamiento. |
| Navegación administrativa | Conservar módulos, replantear composición y móvil. | Las tareas ya están definidas y son adecuadas para trabajar. |
| Títulos grandes con palabras coloreadas | Sustituirlos en gestión por encabezados compactos y directos. | Hoy consumen espacio y compiten con los datos. |
| Personas como mosaicos de explorador | Proponer tablas o listas de entidades como vista principal. | El centro debe comparar identidad, DNI/matrícula y estado, no reconocer iconos de archivo. |
| Portales dentro de la base pública | Proponer una base de consulta propia con marca compartida. | El encabezado comercial y el pie completo alargan cada tarea. |
| Estilos por template | Consolidar una gramática compartida. | Las variantes inline ya producen inconsistencias y fallos responsive. |

Las vistas alternativas de archivos pueden conservarse como herramientas secundarias. Cambiar la presentación principal no implica quitar agrupaciones, búsqueda, rutas ni permisos.

## Lenguaje visual

### Color

Una interfaz clara se adapta al trabajo de oficina del centro durante el día. Propuesta: superficies blancas, fondo con un leve matiz frío y una zona de navegación identificada con el azul institucional. El canvas del visor conserva su superficie oscura, separada del resto de la aplicación.

| Rol | Tratamiento propuesto |
|---|---|
| Identidad y acciones principales | Azul D.O.C. `#004B64`, presente en navegación y botón principal. |
| Marca secundaria | Turquesa del isotipo `#00ADB5`; variantes más oscuras para texto y controles cuando lo exija el contraste. |
| Detalle de marca | Coral `#F66D68` en el isotipo y apariciones institucionales acotadas. |
| Contenido | Texto azul grisáceo oscuro sobre superficies claras; secundarios con contraste real suficiente. |
| Selección | Fondo turquesa suave, contorno o indicador y estado accesible. |
| Estados | Éxito, advertencia y error con sus propias parejas de texto/fondo y etiquetas explícitas. |

Los hexadecimales anteriores provienen del isotipo actual y son referencias provisionales. No se fijan nuevos valores de marca antes de revisar el material del cliente. El coral no se usa como código universal de error o como decoración en todos los botones. Cada pareja de texto y fondo se comprobará, incluyendo avisos, estados y controles deshabilitados cuando correspondan.

### Tipografía y densidad

Una sola familia sans legible para títulos, controles, texto y datos. Sin tipografía impuesta, la pila de sistema actual —Segoe UI y equivalentes— es una base viable para el primer prototipo; la elección final puede hacerse con el marketing. El wordmark queda fuera de esta decisión.

Escala de referencia para gestión: texto de 14–16 px, etiquetas y metadatos de 13–14 px, títulos de sección de 18–20 px y título de pantalla de 26–30 px. Números tabulares para DNI, fechas, tamaños y recuentos. Nombres completos y datos esenciales no se reducen a tamaños microscópicos ni se cortan para sostener un layout.

Las tablas permiten mayor densidad en PC, con filas claramente separadas y acciones previsibles. En teléfonos cambian de estructura y conservan identidad, fecha, estado y acción; no se achica toda la pantalla como una imagen. Controles táctiles de unos 44 px y campos editables de al menos 16 px en móvil.

### Formas y movimiento

Radios moderados, aproximadamente 6–8 px en controles y 10–12 px en superficies que realmente agrupan información. Separadores finos y sombras reservadas a capas flotantes. Una ficha o decisión puede tener un contenedor; cada dato dentro de ella no necesita su propia tarjeta.

Iconografía de trazo uniforme para acciones y navegación. Los nombres de módulo siempre acompañan a los iconos. La imagen dental es contenido clínico; no se reemplaza por dientes decorativos, cruces o ilustraciones de stock.

Movimiento breve para mostrar cambios de estado y apertura de contenido. Sin elevación general de botones, entradas animadas de todo el panel ni esperas visuales al cargar una pantalla. Las preferencias de movimiento reducido conservan la información y el resultado de cada acción.

## Rasgo propio: contexto del estudio siempre reconocible

La continuidad característica es una cabecera de contexto con **Paciente · Estudio · Acceso**. Cambia su contenido según la etapa, pero conserva posición, jerarquía y vocabulario. No añade una etapa nueva ni representa una publicación ficticia.

- Al cargar: identifica la carpeta y la etapa real de transferencia/análisis. No muestra un paciente como confirmado antes de detectarlo.
- Al revisar: nombre y DNI, tipo/fecha, odontólogo seleccionado y consecuencia prevista de confirmar.
- En detalle: identidad del paciente, fecha/tipo, estado real y accesos vigentes.
- En consulta y visor: conserva identidad y estudio con menos información administrativa y acciones según el rol.

Esto une las superficies por información clínica reconocible, sin copiar una interfaz de equipos de rayos o disfrazar el sistema como una historia clínica de papel.

## Cómo se aplica a cada familia de pantallas

| Familia | Dirección propuesta |
|---|---|
| Cargar estudio | Cabecera compacta; pendientes que necesitan intervención; selección de carpeta como tarea central; actividad reciente debajo. Progreso y etapa permanecen claros. |
| Confirmar importación | Resumen de paciente/estudio primero, correcciones bajo demanda, selector de derivante a ancho útil y cierre explícito sobre destinatario y publicación. |
| Estudios | Lista o tabla centrada en paciente, tipo, fecha, estado y acceso al detalle. Filtros y agrupaciones preceden únicamente a los registros que afectan. |
| Pacientes y odontólogos | Tablas de entidades en PC; filas o tarjetas compactas en móvil. Identidad principal y DNI/matrícula visibles. Estado de cuenta separado del permiso de un estudio. |
| Alta y edición | Secciones breves, etiquetas persistentes, campos compartidos y ayudas junto a la decisión. Evitar repetir toda la explicación institucional a ambos lados. |
| Detalle de estudio | Contexto clínico al inicio; visor y archivos; acceso y acciones administrativas separados. Corrección, revocación y eliminación conservan sus consecuencias explícitas. |
| Portal profesional | Mis estudios autorizados como contenido central; búsqueda y filtros primero. Métricas existentes secundarias cuando ayuden; sin inventar actividad, porcentajes ni gráficas. |
| Portal paciente | Mis estudios con fecha, tipo y acceso a visualizar. Ayuda breve. Descargas solo cuando el rol y los permisos actuales las permiten; en la implementación actual el paciente no descarga archivos. |
| Archivos de consulta | Identidad y estudio al inicio; listado legible; acciones compatibles por archivo. Vista de mosaicos útil para imágenes, no obligatoria para todos los formatos. |
| Visor | Más espacio para la imagen, controles legibles y agrupados; información de estudio compacta. En móvil, selección y controles cerca del canvas, sin una introducción que empuje la imagen demasiado abajo. |
| Login, registro y recuperación | Una entrada breve, marca presente y formulario visible pronto en móvil. Mantener explicación de habilitación profesional y ayuda para acceso del paciente. |
| Landing institucional | Mayor libertad de composición y fotografía, con la misma familia tipográfica y color de marca. Servicios, centro y contacto reales; acceso a estudios fácil de encontrar. |

### Primera pantalla de referencia: confirmar un estudio

La pantalla que debe demostrar la dirección es la confirmación: contiene identidad clínica, datos, búsqueda, selección, estado y una consecuencia que debe ser inequívoca. Un rediseño que solo se vea bien en una lista vacía no demostraría el sistema.

En PC: navegación de módulos a la izquierda; encabezado corto arriba del área de trabajo; resumen clínico en la parte superior; datos/corrección y derivante en bloques consecutivos o dos zonas si el ancho permite leer ambos; cierre visible con resultado previsto y botón. La altura del contenido dicta si hace falta scroll: no se promete que todos los estados quepan sin él.

En móvil: encabezado con menú, una sola columna y orden estable —paciente, estudio, derivante, consecuencia, acción—. La barra lateral desaparece del espacio de trabajo. Los avisos y campos se apilan, sin botones con mínimos superiores al contenedor. Si hay una barra de cierre fija, no puede tapar campos, mensajes ni foco; se preferirá un cierre en flujo antes de introducirla.

Ejemplo de composición textual, sin datos reales:

```text
D.O.C. / Estudios / Revisar estudio

[Paciente: nombre y DNI]  [Estudio: tipo y fecha]

Datos detectados                     Odontólogo derivante
Corregir datos                       Buscar por nombre o matrícula
                                     Nombre completo · matrícula

Antes de confirmar
Destinatario: profesional seleccionado
Resultado previsto: publicación sujeta a verificaciones

Cancelar                     Confirmar y publicar
```

El rótulo final es una propuesta de claridad. Debe corresponder al flujo real: si no hay derivante, proponer «Guardar como borrador»; si lo hay, «Confirmar y publicar» solo cuando el backend permite ese resultado. Si la verificación mantiene el estudio en revisión, el éxito informa ese estado. Seleccionar «Asignar más tarde» no se presenta como guardar sin un envío confirmado.

## Qué haría que el resultado pareciera genérico

- Un inicio dominado por tres o cuatro tarjetas de cifras en lugar de la carga, revisión o búsqueda que necesita el centro.
- Gráficas de actividad sin una necesidad y sin datos implementados.
- Grandes frases promocionales dentro de las pantallas de trabajo.
- Fondos con degradados decorativos, vidrio, halos, sombras en cada componente y acentos saturados para estados inactivos.
- Mosaicos iguales para personas, estudios y archivos, que ocultan diferencias de dominio.
- Una navegación comercial y un footer completo repetidos detrás de cada consulta.
- Convertir el lenguaje odontológico en terminología tecnológica o copiar un panel ajeno cambiándole el logo.

## Contenido, estados y límites

Mantener el español rioplatense y nombres de acciones que expresen resultados: cargar, revisar, guardar, publicar, dar acceso, revocar. Los títulos pueden ser directos —«Pacientes», «Editar paciente», «Revisar estudio»— conservando el trato cercano en ayudas. Fechas visibles en un formato consistente, sin cambiar el valor de los controles nativos.

Preparar el diseño con nombres largos, muchos archivos, búsquedas sin resultados, lista vacía, errores de validación, selección no disponible, procesamiento pendiente, revisión necesaria, fallo de red, pérdida de acceso y estudio eliminado. El selector remoto admite hasta 20 resultados por página según el critique; debe seguir siendo legible a esa carga. Su identidad debe ocupar una columna flexible, alineada con los elementos que realmente genera el JavaScript.

El diseño debe distinguir «no se pudo consultar el estado» de «la carga falló». La interfaz no promete recuperación de transferencias abandonadas ni limpieza inmediata de almacenamiento si el servidor no las garantiza. «Worker» y «MinIO» se sustituyen en mensajes operativos por explicación y acción verificables; los detalles técnicos permanecen en diagnóstico.

Un éxito de publicación no equivale a habilitar una cuenta; una cuenta habilitada no equivale a acceso a todos los estudios. Estos hechos deben seguir separados visualmente. Los controles de revisión, reemplazo y eliminación no se simplifican ocultando sus consecuencias.

## Organización propuesta para una implementación posterior

Conservar Django, los templates, servicios y visor existentes. La modernización puede empezar con componentes y tokens compartidos; no requiere migrar a otro framework.

Proponer cuatro capas: tokens base D.O.C.; componentes comunes —campos, botones, estados, avisos, tablas, selección, paginación—; bases por uso —institucional, gestión, consulta, visor—; layouts de tareas. Los templates mantienen formularios, CSRF, valores, validación y permisos. Las vistas de datos dejan de depender de copias inline del explorador.

Secuencia recomendada:

1. Revisar marketing y cerrar los rasgos de marca.
2. Prototipar confirmación de estudio en PC y móvil con datos sintéticos identificados como tales.
3. Extender a una lista con registros reales en estructura y a detalle con archivos/permisos, para validar densidad y estados.
4. Consolidar componentes y registrar el sistema aprobado en `DESIGN.md` y su esquema de tokens.
5. Aplicar a carga, fichas y edición; después portales, acceso y visor; por último ajustar la landing institucional.
6. Verificar los problemas P1 del audit/critique, teclado, contraste, 320 px, 200 % de texto, nombres largos y estados de error. Repetir la auditoría después de implementar.

## Decisiones pendientes y riesgo

El riesgo principal de una dirección sobria es producir una pantalla excesivamente gris o perder la cercanía del centro. Se evita con una zona institucional azul, texto preciso, la marca reconocible y la continuidad de contexto clínico. La sobriedad debe mejorar lectura y decisión; no consiste en quitar todo carácter.

Falta el material de marketing del cliente. Se revisarán versiones oficiales del logo, proporciones, colores, tratamientos tipográficos, fotografías, composiciones y tono. No se trasladará automáticamente la densidad de una pieza publicitaria a una pantalla de gestión. La idea de claridad clínica es preliminar; el branding exacto y el primer prototipo quedan pendientes de esa evidencia.

El proceso de Impeccable no obtuvo referencias externas de su catálogo incluso después del reintento con acceso de red. La propuesta se apoya en material local, el frontend y los informes; no se presenta como contrastada con tableros externos del catálogo.
