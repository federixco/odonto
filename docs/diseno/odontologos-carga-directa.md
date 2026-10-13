# Odontólogos derivantes: carga directa

Implementación y polish del 6 de octubre de 2026. Extensión de «claridad clínica» para administración (Operate), con semilla heredada `ceada702`. El contrato de superficie está en `.impeccable/surfaces/templates-usuarios-odontologo-lista-html-8a5acf6e.md`. Este documento registra el código terminado, incluida la unificación del sidebar administrativo autorizada por el usuario; no redefine la identidad global.

## Presentación y continuidad visual

La lista reutiliza `confirmation.css` y el shell administrativo existentes: Segoe UI, azul D.O.C. (`#004b64`), turquesa de interacción (`#007d85`), documento blanco, lienzo clínico (`#f4f7f8`), bordes finos y foco visible. El título conserva 28px en escritorio y 26px en móvil; nombres usan 15px, datos 14px y metadatos 13/12px. Los campos conservan 16px y 46px mínimos; las acciones compactas de fila usan 44px. Los documentos permanecen planos, con radio de 12px; no se generaron rasters ni activos de producción.

El explorador recupera Lista, Detalles, Mosaicos e Iconos grandes. El selector nombra la vista actual, muestra cuatro opciones con `aria-pressed` y comunica apertura con `aria-expanded`; Escape lo cierra y devuelve el foco al botón, al igual que elegir una vista. Reutiliza `file_view.js`, las cuatro clases `view-list`, `view-details`, `view-tiles`, `view-icons` y la preferencia existente `doc_file_view_mode`. La interfaz local sincroniza etiqueta y estados accesibles sin reemplazar el motor compartido. Sin preferencia válida se muestran Mosaicos; si el navegador bloquea almacenamiento, cambiar la vista sigue funcionando.

Detalles reúne profesional, usuario, matrícula, contacto, estado y acciones en una tabla. Lista presenta registros compactos; Mosaicos organiza tarjetas con contacto; Iconos grandes prioriza identidad y matrícula. A 680px Lista y Detalles pasan a registros apilados, Mosaicos a una columna e Iconos a dos, conservando acciones y estados escritos. La búsqueda sigue siendo GET nativo con `q`, por nombre, apellido, matrícula o correo; la paginación conserva la consulta. Ficha, edición, registro y acceso a Carga de estudios permanecen disponibles. El nombre y «Ver ficha» son enlaces explícitos para que las acciones de carga convivan en cada registro.

El sidebar compartido de `admin.css` usa rail blanco, activo pale (`#edf6f6`), texto navy (`#004b64`) y borde fino (`#a9c0c8`) en Carga, Estudios, Pacientes, Odontólogos y Confirmación. Sólo el módulo actual usa `aria-current="page"`; Carga no conserva una segunda selección. Se retiraron los overrides azules de confirmación y los particulares de odontólogos. Hover y foco emplean teal; el foco compartido es de 2px, mientras `.confirmation-page` conserva su foco general de 3px. La navegación plegable existente a 900px conserva su menú navy. Las URLs versionadas de `admin.css` y `confirmation.css` evitan que un CSS anterior restablezca el sidebar azul.

El color acompaña una identidad escrita, conforme a **The Visible State Rule**. La lista y la preparación conservan **The Flat Work Surface Rule**. El resaltado del destino activo (`#c8ecec`) es una decisión local de interacción, no un nuevo token global.

## Preparación y carga

Sólo los registros de cuentas `HABILITADA` ofrecen destino y botón «Cargar estudio» en las cuatro vistas. Arrastrar una carpeta o archivos muestra nombre y matrícula del destino. Soltar fuera de un registro habilitado no inicia una carga. La alternativa manual permite elegir carpeta o archivos; la lectura de carpetas reutiliza el lector existente y rechaza varias carpetas en una misma selección.

La preparación se antepone al explorador y recibe foco. Muestra derivante, origen de la selección, cantidad y tamaño. Soltar o elegir archivos sólo prepara: el envío requiere «Cargar y analizar». El destino se identifica por id en ambas presentaciones DOM, por lo que cambiar de vista mantiene la selección visible. Antes del envío se puede cancelar la selección; el foco vuelve a «Cargar estudio» del destinatario visible en la vista elegida. Durante lectura o carga se bloquea cambiar el destinatario; una carga pendiente debe reintentarse o cancelarse mediante el motor.

`importacion.js` añade únicamente una API de siete líneas: `docImportacion.cargar`, `leerEntrada` y `ocupada`. Se reutilizan exactamente el procesamiento, rutas relativas, protocolo multipart, UUID de solicitud, progreso, reintento y cancelación originales. La nueva interfaz no duplica el transporte ni el análisis.

## Revisión y confirmación

La redirección al detalle incorpora `derivante` y `origen=odontologos` en GET. El contexto se guarda en `sessionStorage` con una clave que incluye usuario administrador e importación. Esa persistencia permite continuar tras el POST nativo de creación de paciente y conservar cambios o una selección vaciada tras errores de confirmación. Si el almacenamiento de sesión no está disponible, el formulario conserva su selección pero puede perderse la continuidad entre pantallas.

La presentación contextual sólo se activa para ese origen o su contexto persistido. Muestra el derivante verificado y permite «Cambiar odontólogo o acceso». Una selección no disponible queda corregible y no se presenta como verificada. Tras un error nativo prevalece el valor devuelto por el formulario.

En el formulario principal, tipo o fecha vacíos pasan a «Completá los datos faltantes». Los datos detectados siguen editables bajo revisión. Cuando no existe una ficha coincidente, continúa el formulario nativo: nombre, apellido o DNI detectados y sin error se agrupan bajo «Revisar datos detectados»; los faltantes o erróneos quedan visibles. Crear el paciente sigue siendo un POST obligatorio antes de continuar; también permanece la búsqueda nativa de una ficha existente.

No hay envío automático ni publicación automática. Crear la ficha no publica el estudio. La confirmación conserva permisos, validaciones, revisión de estudios y bloqueo de pacientes mezclados; limpiar el derivante conserva la consecuencia de borrador. El resultado final depende del servidor.

## Alcance del código

- `apps/usuarios/templates/usuarios/odontologo_lista.html`: registro, destinos y preparación.
- `apps/usuarios/templates/usuarios/includes/odontologo_acciones.html`: acciones compartidas por tabla y registros del explorador.
- `static/core/css/odontologos.css`: extensión local de lista y revisión contextual.
- `static/core/js/odontologo_carga.js`: preparación y delegación al motor.
- `static/core/js/odontologo_confirmacion.js`: contexto y organización de campos.
- `apps/estudios/templates/estudios/importacion_detalle.html`: incorporación del script contextual.
- `static/core/js/importacion.js`: exportación de la API existente.
- `static/core/css/admin.css`: sidebar compartido y estado activo único.
- `static/core/css/confirmation.css`: retiro de overrides del sidebar; se preserva el resto de confirmación.
- `templates/core/admin_base.html` y `apps/estudios/templates/estudios/importacion_detalle.html`: versiones nuevas de CSS compartido y confirmación.

La evidencia inicial de `.local/odontologos-before/protected.json` correspondía a la primera extensión de carga. El polish conserva backend, configuración, modelos, base de datos, permisos, rutas y motores existentes, incluidos `importacion.js`, `file_view.js` y confirmación. La excepción visual expresamente autorizada es el sidebar compartido y sus versiones de CSS. La documentación actualiza únicamente ese componente en `DESIGN.md` y `.impeccable/design.json`, además de este documento; conserva `PRODUCT.md`. Los cambios previos de landing, acceso y `.gitignore` no pertenecen a este polish.

Hay deriva documental previa: la narrativa del sidecar aún describe la interfaz pública anterior, mientras `DESIGN.md` ya referencia la landing. La revisión también registra reflow deficiente de Carga original a 390px. Ambos quedan informados y sin reparación; no se incorporan como reglas del sistema.

## Verificación y límites

La primera revisión de carga directa emitió `ship`: su evidencia histórica incluye 33 comprobaciones de `checks.json`, cuatro de `behavior.json` y 28 capturas de lista, preparación, progreso, confirmación y errores. Esa revisión precede a la recuperación de las cuatro vistas.

La revisión independiente del polish está en `.impeccable/review/odontologos-polish/finish-review.md`. `checks.json` registra 65 comprobaciones correctas sobre las cuatro vistas, preferencia, búsqueda/paginación, teclado, destinatario compartido y sidebar uniforme; `transport/checks.json` registra diez sobre preparación, bloqueo del destinatario, progreso y protocolo de carga simulado. El reviewer inspeccionó 18 capturas del explorador y navegación, más cinco de transporte a 1440/390; Iconos también se comprobó a 1024. La comparación funcional usa `.local/odontologos-polish-before/previous.html` y `current.html`. No había comp aprobado ni Quality Bar externo: la continuidad Operate y la semilla heredada guían esta extensión.

La disposición inicial del polish fue `fix`: invalidar la URL anterior de `confirmation.css` y reconciliar la documentación con el sidebar implementado. La URL se actualizó y este documento registra el sistema terminado; la disposición de cierre corresponde a la revisión posterior, no se infiere de esos arreglos.

El polish volvió a pasar los 45 tests Django de `apps.usuarios.tests.test_odontologos`, `apps.estudios.tests.test_views` y `apps.estudios.tests.test_lotes_mezclados`, con `config.settings.test` y base aislada, según `project-tests.txt`. La ampliación histórica de 92 tests bajo SQLite registró diez errores por bloqueos que requieren MySQL, un fallo de limpieza y tres omisiones; no se modificó backend para resolverlos.

El servidor QA de puerto 8003 usó fixtures sintéticos en memoria. Los endpoints de carga y PUT se simularon; estas comprobaciones no validan almacenamiento MinIO real, ejecución real del worker ni publicación efectiva. El error de fecha sí recorrió validación de formulario mediante POST nativo con un archivo sintético `COMPLETO`. Las otras variantes con cero archivos completos sólo prueban presentación. No hubo POST de producción ni nuevos datos reales. Capturas y scripts de `.local`/`.impeccable/review` son evidencia temporal ignorada y no se incorporan al commit.

Para validar el circuito real en un entorno de prueba, levantar Django, MySQL, MinIO y el worker configurados; usar un estudio de prueba conocido. Comprobar preparación sin POST al soltar, envío explícito, progreso real, interrupción/reintento del mismo lote y cancelación confirmada. Revisar paciente, tipo, fecha y derivante; probar creación de paciente, corrección, vaciado y errores nativos. Confirmar manualmente y comprobar el estado devuelto, acceso autorizado y archivos almacenados. Contrastar también Carga de estudios original, lotes mezclados y revisión pendiente.
