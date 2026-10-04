# Cancelación, reintentos, concurrencia y análisis en segundo plano

Fecha: 03/10/2026. Rama de trabajo: `fix/errores-criticos`.

## Cambios implementados (pendientes de pruebas funcionales)

- La importación responde **202** cuando encola el análisis; no analiza la carpeta dentro de la petición web. El detalle consulta estado/progreso cada tres segundos (cada cinco si la pestaña está oculta).
- El worker calcula SHA-256 en bloques y luego inspecciona metadatos. Los hashes de las carpetas se verifican antes de dejar el lote pendiente de confirmación. La carga individual/reemplazo mantiene su verificación sincrónica.
- La cola usa el JSON existente del lote: reserva temporal de 180 segundos, token por intento, renovación durante lecturas y comprobación bajo bloqueo antes de persistir resultados. Un worker anterior no puede confirmar resultados después de una cancelación o recuperación de su reserva.
- Tres intentos automáticos de análisis, con espera creciente. Un proceso interrumpido deja una reserva recuperable; agotados los intentos el lote queda en ERROR y permite reintento manual.
- Cancelar es POST, conserva trazabilidad y rechaza importaciones confirmadas. El worker aborta multipartes y elimina los objetos de los lotes cancelados, por lotes pequeños. Conserva los identificadores de cargas cuyo aborto no fue confirmado.
- Completar un archivo dos veces devuelve éxito sin ensamblar ni borrar otra vez. Cada carga de carpeta tiene token de intento; un token anterior no completa una nueva carga.
- Exclusión de operaciones por archivo y por iniciador mediante bloqueos de sesión MySQL, sin transacciones abiertas durante operaciones S3. Recursos ocupados devuelven 409 reintentable.
- El navegador ofrece Cancelar/Reintentar, aborta XHR y fetch, usa tiempos máximos y esperas crecientes; conserva los archivos y las partes de la sesión para recuperar respuestas perdidas. Los archivos ya completados no se duplican ni se vuelven a subir.
- Los inicios aceptan UUID de solicitud para evitar duplicados ante respuestas perdidas. Reutilizarlo con otra carpeta/archivo se rechaza. Las carpetas no pueden superar la cantidad ni el tamaño total declarados.
- Se reserva la fila de una carga individual antes de llamar a S3 para impedir la publicación durante su preparación. Publicación y registro de paciente revisan el estado bajo bloqueo.
- Selectores de pacientes, derivantes y profesionales a autorizar: búsquedas en servidor, 20 resultados por página, orden estable, espera de 250 ms y descarte de respuestas obsoletas. La selección se mantiene al cambiar filtros/página. DNI exacto se consulta fuera de la primera página. Nombres se representan como texto, no HTML.
- Consultas de estado/búsqueda requieren administrador; el estado de un lote exige además ser su iniciador y no expone tokens ni metadatos clínicos.

## Arranque local

`reiniciar_sistema.ps1` inicia ahora también el trabajador (oculto), junto con Django y MinIO. No se ejecutó durante esta corrección.

Para iniciar únicamente el trabajador, desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe manage.py procesar_importaciones
```

Para procesar un trabajo y una pasada de limpieza y terminar:

```powershell
.\.venv\Scripts\python.exe manage.py procesar_importaciones --una-vez
```

Estos comandos **sí modifican los lotes encolados y limpian los cancelados**. No ejecutarlos contra datos que se quieran preservar sin revisar su estado. Ctrl+C detiene el worker; las reservas se recuperan al vencer. Logs del arranque habitual en `.local/logs/worker.out.log` y `worker.err.log`.

No hay migraciones, nuevas tablas, Redis, Celery ni dependencias nuevas. Se requiere MySQL 8.4 y acceso a S3/MinIO. El worker debe estar activo: sin él las carpetas quedan esperando análisis y la limpieza queda pendiente.

## Verificación realizada

Se verificó sintaxis Python/JavaScript/PowerShell, compilación de plantillas e importación de rutas y comando, **sin conexión a la base**. No se ejecutaron pruebas funcionales ni de concurrencia, no se iniciaron servicios, no se aplicaron migraciones y no se hizo commit/push.

## Pruebas preparadas para ejecutar después

Las nuevas suites cubren cola/reservas, estados terminales, respuestas perdidas, idempotencia, token antiguo, cancelación con S3 inaccesible, hashes interrumpibles, buscadores paginados y exclusión real entre conexiones MySQL. Incluyen dos completados simultáneos y cancelar mientras se verifica un archivo. El almacenamiento está simulado: no eliminan objetos del bucket real.

```powershell
.\.venv\Scripts\python.exe manage.py test apps.estudios.tests.test_cargas_asincronas apps.archivos.tests.test_transferencias_reintentables apps.estudios.tests.test_integridad_transferencias apps.estudios.tests.test_revision_pendientes --settings=config.settings.test_mysql
```

Después, ejecutar toda la regresión con el mismo settings MySQL y probar manualmente un lote real con MinIO, interrupción de red, cancelación, reintento y dos sesiones. El runner crea una base MySQL de pruebas con nombre aleatorio; requiere permiso para crearla/eliminarla. No utilizar SQLite ni `--keepdb` para sustituir estas pruebas.

## Límites operativos a tener en cuenta

- Los archivos del navegador y sus ETags se conservan durante la sesión de carga, no después de recargar/cerrar la página. El análisis encolado sí sobrevive a la salida de la página y al reinicio del servidor.
- La cancelación del servidor es cooperativa: espera a que termine la lectura S3 en curso, con timeouts. No detiene instantáneamente el proceso Python ni deshace estudios confirmados. Una carga individual completada se conserva si Cancelar llega tarde.
- Si MinIO no está disponible, la limpieza queda pendiente y vuelve a intentarse. Las cargas sin identificador registrado por una caída justo durante la creación multipart requieren política de expiración de multipartes incompletos en el almacenamiento; no se promete limpieza de esos huérfanos sin registro.
- Para producción se debe supervisar el worker (systemd/supervisor/contenedor), configurar timeouts del proxy para cargas individuales y una política de multipartes incompletos; monitorizar cola/errores/limpieza y medir rendimiento con el volumen real. La cola en JSON evita cambios de esquema ahora, pero para gran volumen conviene una cola o tabla de trabajos indexada.
- Los bloqueos elegidos son cooperativos y válidos para una única instancia de servidor MySQL compartida por los procesos. No equivalen a coordinación entre distintos servidores MySQL. Referencia técnica: [MySQL 8.4: funciones de bloqueo](https://dev.mysql.com/doc/refman/8.4/en/locking-functions.html).
