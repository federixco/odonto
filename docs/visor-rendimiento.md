# Carga DICOM: caché 2D y preparación 3D

## Problema y cambio

El visor anterior liberaba los demás cortes al navegar en 2D. Volver al corte
anterior podía repetir su descarga y decodificación. El volumen 3D esperaba cada
corte antes de solicitar el siguiente; la latencia de red se acumulaba.

Ahora cada apertura de una serie dispone de una caché **en RAM**, con precarga
de cortes cercanos y prioridad para el corte solicitado por el usuario. Una
serie pequeña se precarga completa; una grande utiliza una ventana móvil.
Los cortes recientes se conservan hasta necesitar espacio. No se promete que
una serie arbitrariamente grande quepa completa en memoria.

El volumen 3D carga hasta cuatro cortes simultáneamente (también limitado por
`VISOR_CONCURRENCY`). Escribe cada uno en su posición espacial, aunque termine
fuera de orden, y libera el original después de incorporarlo al volumen.
El progreso muestra cortes completados/total. Un corte fallido impide mostrar
un volumen incompleto. La espera por carga/decodificación tiene un límite de
60 segundos; se puede cerrar y reintentar.

## Memoria y acceso

- El presupuesto es el menor entre `VISOR_MAX_VOLUME_BYTES` y una fracción de
  la memoria del dispositivo. Si el navegador no informa RAM se usa un valor
  conservador. No equivale a un límite absoluto del proceso del navegador/GPU.
- Django informa `decodedBytes` por frame a partir de filas y columnas. La
  caché reserva espacio para originales, píxeles y buffers de trabajo.
- La planificación 3D reserva memoria para todas las cargas simultáneas y
  adapta la resolución del volumen. Los cortes 2D conservan su resolución.
- La caché pertenece a la apertura actual: se libera al cerrar, cambiar de
  serie/modo o abandonar la página. No usa IndexedDB ni localStorage.
- Se mantienen las URLs privadas, la autorización de descargas y la ausencia
  de cookies del portal en el almacenamiento externo.
- Mientras una vista ya está abierta se vuelve a validar el acceso cada 30
  segundos, con 15 segundos de espera máxima. Una revocación detectada cierra
  la vista y libera la caché. No revoca retroactivamente bytes ya descargados.

## Compilación y verificación

Después de actualizar estos cambios en otra PC hay que ejecutar `npm ci` si
faltan dependencias y `npm run build`. Los archivos de `static/visor/dist` son
generados e ignorados por Git. En despliegues que lo requieran, ejecutar luego
`collectstatic` y renovar los recursos estáticos servidos.

Pruebas:

- `npm test`: caché, deduplicación, prioridad, presupuesto de memoria,
  concurrencia, cancelación, reconstrucción y parsers STL/PLY.
- `npm run test:browser`: usa archivos sintéticos, el visor compilado real y
  dos servidores HTTP locales que simulan portal y almacenamiento privado.
  No necesita una base de datos ni MinIO. La configuración cargada es MySQL;
  no se utiliza SQLite. En PowerShell puede seleccionarse Edge instalado con
  `$env:VISOR_BROWSER_CHANNEL='msedge'`.
- `python manage.py test apps.estudios.tests.test_visor.DicomMetadataTests
  --settings=config.settings.test_mysql`: metadatos y contrato de memoria sin
  acceso a la base.

Las pruebas de navegador cubren reutilización 2D, multiframe, RLE, 3D adaptado,
latencia simulada, fallos, reintentos, cancelación, revocación y liberación de
recursos. No sustituyen medir el estudio real desde otra conexión: el ancho
de banda de subida, el túnel y la capacidad gráfica del cliente siguen
influyendo en el tiempo total.
