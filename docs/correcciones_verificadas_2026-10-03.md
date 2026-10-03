# Correcciones y verificación — 03/10/2026

Rama: `fix/errores-criticos`. Base del trabajo: `f9e5abc`.
Cambios locales, sin commit, push ni cambios de rama.

## Resultado

La suite completa ahora pasa sobre MySQL: **245 pruebas, sin fallos ni errores**.
La ejecución anterior tenía 228 casos, con 3 fallos y 19 errores. Se corrigieron
los tests desactualizados y se agregaron 17 regresiones; no se eliminaron las
restricciones de integridad para hacer pasar pruebas.

Comando utilizado:

```powershell
$env:CARGA_LOG_ENABLED = 'false'
.\.venv\Scripts\python.exe manage.py test --settings=config.settings.test_mysql --noinput --verbosity 1
```

Django creó y destruyó una base temporal independiente. No se aplicaron
migraciones ni limpiezas contra la base habitual. Las operaciones S3 fueron
simuladas: el nuevo runner bloquea el transporte real de botocore y la
configuración de pruebas no hereda credenciales ni buckets de `.env`.

## 1. Correcciones de la suite

- Descargas: `TransactionTestCase` permite comprobar el cierre real de
  `FileResponse` sin que `request_finished` rompa la transacción envolvente de
  `TestCase`. Se conservan las comprobaciones de contenido, permisos y cierres.
- Paginación: cuentas ficticias con contacto y estudios publicados con fecha.
- Cancelación: se simulan aborto y eliminación de S3. Un test independiente
  comprueba que la limpieza fallida devuelve 503 y conserva el upload para
  reintentar.
- Inicio duplicado: se verifica HTTP 200/idempotencia, sin crear ni abortar otra
  transferencia y sin alterar el archivo completo existente.
- Selector: se comprueba el endpoint AJAX y el identificador del profesional,
  no opciones que ya no se incluyen en el HTML inicial. Los accesos ya asignados
  sí siguen comprobándose en el HTML del detalle.

## 2. RAM y ZIP: aclaración del informe anterior

**La lectura del archivo entero en RAM ya estaba corregida antes de este trabajo.**
La expresión «corrección mínima» describía el alcance de la arquitectura,
no un fallo persistente de lectura: el ZIP todavía se prepara en el servidor.

La descripción más precisa es: **RAM acotada para el contenido; ZIP con costos
de disco temporal, CPU y tráfico del VPS**. Un bloque de 1 MiB no significa que
todo el proceso Django consuma solamente 1 MiB: existen buffers de compresión,
metadatos ZIP, consultas y el resto de la aplicación.

Se mantuvo la lectura por bloques, Zip64 y el armado completo antes de responder.
No se cambió a una transmisión que pueda empezar con HTTP 200 y fallar a mitad
del paquete. También se agregaron:

- Una preparación ZIP simultánea por base de datos, con bloqueo MySQL entre
  procesos. Otro intento recibe 409 y `Retry-After: 2`; el usuario debe reintentar.
- Máximo de datos originales y de entradas, para acotar disco y metadatos en RAM.
- Comprobación previa de disco disponible, con margen para DEFLATE/cabeceras y
  una reserva adicional. Falta de espacio: 507, sin comenzar lecturas de S3.
- Compresión de nivel 1 para reducir trabajo de CPU.
- Cierre del cliente S3 y de cada cuerpo; el temporal se cierra al finalizar o
  interrumpirse `FileResponse`. Los fallos de lectura siguen cerrándolo también.

Configuración opcional en el entorno:

| Variable | Valor predeterminado | Finalidad |
|---|---:|---|
| `ZIP_MAX_TAMANO_TOTAL` | 10737418240 bytes (10 GiB) | Datos originales máximos por paquete |
| `ZIP_MAX_ARCHIVOS` | 5000 | Entradas máximas por paquete |
| `ZIP_RESERVA_DISCO` | 536870912 bytes (512 MiB) | Espacio que se intenta preservar |
| `ZIP_TEMP_DIR` | Directorio temporal del sistema | Ubicación del armado |

Superar los límites devuelve 413; no elimina archivos ni bloquea sus descargas
individuales autorizadas. Los ZIP ya preparados pueden descargarse en paralelo:
el bloqueo solo cubre su construcción. Por eso siguen consumiendo disco y ancho
de banda mientras se entregan.

La comprobación de espacio **no es una cuota ni una garantía contra escrituras
de otros programas**. Todavía corresponde dimensionar y monitorizar el VPS,
ajustar sus timeouts y medir exportaciones reales. Preparar ZIP en segundo plano
y almacenarlos privadamente para descargar mediante URL prefirmada sería otra
etapa de arquitectura; no se implementó ni se declaró terminada aquí.

## 3. Varios estudios del mismo paciente

Se comparan `StudyInstanceUID` y fechas en las cabeceras y en todos los registros
STUDY de DICOMDIR. Series diferentes de un mismo estudio no generan este aviso.

Si aparecen estudios o fechas diferentes:

1. Se muestra una advertencia y no se preselecciona arbitrariamente una fecha.
2. El administrador revisa si debe separar las carpetas.
3. Si corresponde agruparlas, debe elegir la fecha y marcar expresamente la
   revisión. Sin eso, no se crea el estudio ni se asocian los archivos.
4. La revisión queda registrada en el JSON de la importación y en la auditoría.

La protección existe también en `ImportacionEstudio.confirmar()` para llamadas
que no pasen por el formulario. No autoriza mezclas de pacientes incompatibles:
esas continúan bloqueadas, aun marcando la revisión de estudios.

**No hay nuevas tablas, columnas ni migraciones.** Se reutiliza el JSON existente.
El método `confirmar` agrega el argumento opcional `estudios_revisados`; los
servicios y formularios agregan validación. `EstudiosLote` es una utilidad Python,
no un modelo persistente. Las importaciones ya analizadas anteriormente no se
reanalizaron en la base habitual: la nueva detección se aplica al analizar lotes.

## 4. Otros arreglos

- Se eliminaron los 224 bytes NUL de `admin.css`, sin modificar el diseño ni los
  selectores. Git puede mostrar un diff amplio por la normalización de finales
  de línea del archivo previamente contaminado.
- Se retiró `delete_file.js`: tenía sintaxis inválida y ninguna referencia activa
  encontrada. La eliminación/corrección vigente usa otros handlers; el archivo
  retirado es recuperable desde Git.
- Se retiró el import duplicado de `Odontologo` en las vistas de estudios.
- El cliente de lectura/hash S3 se cierra también cuando falla `get_object`, y
  se conserva su reutilización dentro de una sesión de análisis.
- Producción rechaza una clave secreta demasiado corta/insegura y hosts vacíos
  o `*`. El entorno local sigue usando sus settings de desarrollo.
- La creación automática de buckets queda limitada a `DEBUG=True`;
  producción exige aprovisionar previamente el bucket privado.
- La limpieza de prueba exige base local y endpoint S3 local explícito, aborta
  multipartes pendientes antes de borrar referencias y conserva la base si no
  se confirma el aborto. No se ejecutó contra datos habituales.
- Se instaló y fijó `s3transfer==0.19.0`, compatible con boto3 1.43.90.

Para sincronizar el entorno de otro desarrollador:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

## 5. Verificación y límites

- Suite MySQL: **245 aprobadas**, 6,782 segundos de ejecución de tests
  (sin contar preparación de la base).
- `manage.py check`: sin problemas.
- `makemigrations --check --dry-run`: `No changes detected`.
- `pip check`: `No broken requirements found`.
- Sintaxis: 143 archivos Python y los 9 scripts JavaScript restantes válidos.
- 42 plantillas HTML compiladas correctamente.

No se hicieron pruebas de navegador, pruebas de carga simultánea con tomografías
reales ni mediciones de RAM/RSS en un VPS. Las regresiones comprueban lecturas
acotadas, límites, estados y cierres; no sustituyen esas mediciones.

Los métodos placeholder y refactorizaciones amplias pendientes no se convirtieron
en funcionalidades nuevas: correo/notificaciones, otras tarjetas y la consolidación
completa de transportes requieren trabajo separado. HSTS, proxy HTTPS, correo,
backups, cuotas y supervisión del worker dependen del despliegue real y no están
certificados por estos tests. El worker `procesar_importaciones` continúa siendo
necesario para analizar carpetas y gestionar tareas pendientes.

La suite aprobada permite continuar las pruebas del proyecto; no constituye una
certificación de seguridad ni aprobación automática para producción con datos
reales de pacientes.
