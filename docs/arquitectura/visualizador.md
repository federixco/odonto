# Visualizador básico D.O.C.

Implementación en `feature/visualizador3D`, sobre la base de seguridad de `2bcd57d`. No modifica modelos ni migraciones. El DER permanece igual.

## Alcance

| Requisito | Implementación | Límites |
|---|---|---|
| RF-19 | Three.js: STL ASCII/binario y PLY ASCII/binario, rotación, desplazamiento, zoom y restablecer. PLY conserva color y admite nubes de puntos. | PLY: propiedades escalares de vértice; caras triangulares/cuadrangulares. Otros elementos/listas se rechazan. No medir, editar ni convertir a STL. |
| RF-17 | Cornerstone: selección de serie y cortes monocromáticos, anterior/siguiente, deslizador, rueda, zoom y desplazamiento. | DICOM Part 10 con sintaxis permitida. DICOMDIR y objetos sin imagen no se renderizan. Un paquete propietario no equivale a una imagen. |
| RF-18 | Viewport volumétrico real de Cornerstone, con preset CT-Bone y navegación básica. No es una malla ficticia. | Geometría consistente CT/MR clásica de un frame por objeto, marco de referencia, al menos tres cortes y presupuesto de memoria. Enhanced/multiframe no habilitan volumen. No es software diagnóstico validado. |
| RF-20 | Paciente titular ve sus estudios publicados. | **Sin descarga individual ni ZIP**, incluso por URL directa. El navegador necesariamente recibe bytes al visualizar; esto no es protección anticopia. |
| RF-23 | Solicitud de apertura + un resultado reportado por cliente por apertura. | El reporte del cliente no certifica que una persona haya leído el estudio. No hay auditoría por frame ni por movimiento. |

Los controles no incluyen medición, segmentación, anotación, planificación ni diagnóstico. La visualización web no reemplaza Galileos/Sidexis. Cada exportación debe probarse con el centro antes de dar por satisfecha su compatibilidad clínica.

## Arranque y compilación

Desde la raíz del repositorio, después de instalar `requirements.txt` y configurar MySQL/S3:

```powershell
npm ci
npm run build
.venv\Scripts\python.exe manage.py runserver
```

En otra consola, con la **misma configuración**:

```powershell
.venv\Scripts\python.exe manage.py procesar_importaciones
```

El worker existente atiende también los pedidos de preparación del visor. Sirve para importaciones anteriores y archivos manuales: no necesita volver a importar el estudio. Sin worker, los modelos STL/PLY funcionan y DICOM informa que está preparando las series.

Entrar al detalle de un estudio y elegir **Abrir visor 3D y cortes**. También hay accesos desde los archivos STL/PLY/DICOM y el portal del paciente.

Al entrar desde un archivo, el catálogo selecciona su modelo o su serie DICOM. Un archivo retirado del estudio deja de ser seleccionable cuando se actualizan las opciones. Durante la navegación de cortes se carga uno por vez y se conserva el último destino elegido en el deslizador, aunque el usuario lo mueva antes de terminar la lectura anterior. Si una nueva lectura recibe un rechazo de sesión/permisos, se cierra el contenido previo y se informa al usuario.

### En el VPS

Node es únicamente una herramienta de build, **no otro servidor**. Usar Node 22.12+ o 24 LTS; se probó Node 24.17.0. La estrategia elegida es **build de despliegue reproducible**:

1. `npm ci` instala exactamente `package-lock.json`.
2. `npm run build` crea `static/visor/dist/` con JS, CSS, workers y WASM.
3. `python manage.py collectstatic --noinput` incorpora esos archivos.
4. Servir los estáticos mediante la configuración existente del VPS. El JS de entrada `visor.js` y `visor.css` no deben llevar una política `immutable` indefinida: revalidarlos al desplegar. Los chunks con hash sí pueden cachearse.
5. Mantener el worker bajo el supervisor de procesos del despliegue.

No versionar `node_modules`, el build, datos clínicos ni capturas de pacientes. No se utiliza CDN en tiempo de ejecución. Las dependencias están fijadas: Cornerstone/metadata/loader/tools 5.11.4, Three.js 0.186.1, Vite 8.3.2. Los overrides de `fflate`, `adm-zip` y `uuid` actualizan dependencias transitivas vulnerables; revisar auditoría y pruebas cuando se cambien versiones. El alias `events` satisface una dependencia de `dcmjs` al compilar para navegador. Los avisos de Vite sobre `fs/path` corresponden a las ramas Node de codecs Emscripten; los WASM de navegador se empaquetan como archivos locales.

## Flujo y seguridad

1. Django valida sesión, cuenta habilitada, rol, publicación y autorización/propiedad.
2. El catálogo devuelve opciones sin URLs S3 y reúne **todos** los archivos, independientemente de la paginación del explorador.
3. Para cada contenido elegido, el navegador consulta una URL estable de Django. Django vuelve a validar y devuelve una redirección a una URL S3 prefirmada de lectura.
4. Los bytes viajan directamente del almacenamiento al navegador. Django no reconstruye ni retransmite el volumen y no prepara ZIP para visualizarlo.
5. Al cambiar/cerrar, se abortan transferencias, se liberan geometrías, cachés, renderizadores, observadores y workers.

La política compartida está en `apps/core/permisos_estudios.py`. Admin habilitado puede abrir borradores/revisión, pero no eliminados. Derivante necesita autorización vigente y publicación; paciente necesita ser titular y publicación. Contenido exige archivo `COMPLETO`, asociado al estudio de la URL. Los archivos de importaciones aún no confirmadas, reemplazados, incorrectos, purgados o ajenos no se firman. Los paquetes DICOM deben pasar además por el índice para no enviar EXE/XML al decoder.

Página, catálogo, metadatos y redirecciones usan `private, no-store`, `no-referrer`, `nosniff` y `Vary: Cookie`. No hay URLs S3 persistidas en DB/localStorage ni errores del proveedor en la auditoría. Las credenciales S3 permanecen en el servidor. En producción sigue vigente el requisito HTTPS/TLS de la configuración existente.

Una URL firmada ya emitida **sigue siendo válida hasta su expiración** (`AWS_S3_PREVIEW_EXPIRATION`, 900 segundos por defecto). Revocar acceso impide una nueva emisión, no invalida mágicamente los bytes que ya llegaron. Ante error, “Volver a intentar” solicita otra autorización; no hay bucles ni reintentos infinitos.

### CORS del almacenamiento

El bucket permanece privado. Añadir a sus reglas existentes una regla de lectura, adaptando el origen exacto del sitio:

```json
{
  "AllowedOrigins": ["https://www.DOMINIO-REAL.com.ar"],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["Range"],
  "ExposeHeaders": ["Content-Length", "Content-Range", "Accept-Ranges"],
  "MaxAgeSeconds": 300
}
```

No copiar el dominio de ejemplo literalmente. Para pruebas locales, usar el origen exacto `http://127.0.0.1:8000` (o el puerto que corresponda), nunca `*`. **Conservar las reglas de upload existentes**: esta regla no reemplaza las de PUT/multipart. CORS no autoriza acceso al objeto; la autorización es la firma. La aplicación usa cookies solo hacia su mismo origen, nunca credenciales cross-origin hacia S3. No se habilitan COOP/COEP globales ni se desactiva la verificación TLS.

## Índice DICOM sin tablas nuevas

`visor_dicom.py` lee cabeceras con pydicom y `stop_before_pixels`, hasta 512 KiB por objeto. No almacena nombres, DNI, fecha de nacimiento ni todo el dataset. Extrae SOP/Study/Series/FrameOfReference, TransferSyntax, dimensiones, orientación, posición, espaciado y escala de intensidad.

Se agrupa por Study/Series/FrameOfReference. Con geometría válida se ordena mediante la proyección de la posición sobre la normal de los cortes, no por nombre de archivo. Se rechaza volumen ante duplicados, inclinación/desplazamiento lateral, huecos/espaciado irregular, orientaciones o escalas diferentes. Sin posiciones confiables, los cortes se ordenan por InstanceNumber y se advierte que no es un orden espacial verificado.

Las cabeceras ilegibles o que excedan el prefijo se informan como omitidas. No se usa `force=True` para interpretar arbitrariamente cualquier archivo. El conjunto permitido incluye Explicit/Implicit VR, Big Endian, RLE, JPEG tradicional, JPEG-LS y JPEG2000; el resultado real de cada decoder se verifica al abrir. Los errores de un objeto no se presentan como un volumen completo.

Se verificaron en navegador cortes y volumen con una serie CT sintética sin compresión y otra con compresión RLE Lossless. También se verificaron cortes de un objeto multiframe SC; ese caso no habilita volumen. Esto no valida automáticamente JPEG/JPEG-LS/JPEG2000 ni Enhanced CT: requieren ejemplos representativos. Los frames de un mismo objeto comparten la transferencia; sus buffers se liberan al cambiar de objeto o cerrar la vista.

`visor.py` mantiene una caché reconstruible en `data/visor/`, fuera de `static` y `media`. `.pedido` indica trabajo pendiente; `.json` contiene índice, huella y resultado. Ambos son técnicos, no entidades de negocio. Los procesos web y worker deben compartir esa carpeta privada con permisos de lectura/escritura; no exponerla mediante Nginx ni Git.

La huella depende de los archivos actuales, hash, tamaño, formato, estado disponible y fecha de actualización, además de la versión/límites del índice. Una corrección/inclusión/reemplazo invalida la caché. El worker usa el bloqueo MySQL existente, no transacciones abiertas durante S3, publica JSON de forma atómica y elimina metadatos vencidos. TTL por defecto: una hora. Si falla S3, se informa error y “Actualizar opciones” permite reintentar. No se elimina ni modifica ningún original.

## Límites iniciales

| Variable configurable por entorno | Valor inicial |
|---|---:|
| `VISOR_MAX_MESH_BYTES` | 80 MiB |
| `VISOR_MAX_VERTICES` | 2.000.000 vértices/índices de triángulos |
| `VISOR_MAX_IMAGE_BYTES` | 64 MiB por objeto DICOM y su estimación descomprimida |
| `VISOR_MAX_VOLUME_BYTES` | 256 MiB de presupuesto estimado |
| `VISOR_MAX_FRAMES` | 1.500 |
| `VISOR_CONCURRENCY` | 4, limitado a 1–4 |
| `VISOR_MAX_FILES` | 5.000 candidatos por índice |
| `VISOR_HEADER_BYTES` | 512 KiB |
| `VISOR_CACHE_TTL` | 3.600 segundos |

La estimación volumétrica reserva Float32 × cuatro copias para reconstrucción/GPU/buffers, más el tamaño de objetos originales. No es una medición exacta de la RAM/GPU ni una garantía contra archivos adversarios. Al superar el límite, se conservan cortes compatibles. No aumentar límites sin medir en el equipo del centro. Una tomografía de cientos de MB puede no admitir volumen con este presupuesto, aunque sí carga/descarga y cortes.

Los parsers de mallas trabajan en worker con límite de tiempo y conteos antes de materializar geometría. DICOM mantiene hasta dos workers de decodificación. En 5.11.4 se evita el atajo `loadAndCacheImage` en precarga: deja sin observar una promesa rechazada al cancelar. El adaptador espera explícitamente la carga y su registro en caché; el viewport recibe imágenes preparadas. No se modifica `node_modules` ni se suprimen globalmente errores del navegador.

## Pruebas

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings.test
.venv\Scripts\python.exe manage.py test --settings=config.settings.test_mysql --noinput
npm test
npm run build
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD/.local/pw-browsers"
npx playwright install chromium
npm run test:browser
```

Las pruebas Django crean la base temporal definida por `test_mysql`, con S3 simulado/bloqueado. Las de navegador levantan un servidor **solo loopback** con el template/build reales y archivos sintéticos, más otro puerto que simula S3. No usan usuarios, buckets o pacientes reales. Requieren puertos 8765/8766 disponibles.

Si se mantiene manualmente el servidor sintético con `python -m tests.visor_browser_server`, ejecutar las pruebas con `$env:VISOR_TEST_EXTERNAL_SERVER='1'`. Para la matriz ampliada, instalar Firefox de Playwright, tener Chrome/Edge instalados y usar `$env:VISOR_BROWSER_MATRIX='1'`.

Ver el [informe de verificación](verificacion-visualizador.md) para resultados, entorno y pendientes. El diagnóstico inicial de almacenamiento local devolvió `NoSuchKey`: existen registros en MySQL sin objetos correspondientes en el MinIO disponible. No se borraron ni alteraron esos registros. Se necesita volver a disponer de una exportación representativa para verificarla privadamente; no declarar compatibilidad con ella basándose en fixtures sintéticos.

## Documentación y diagrama de clases

Agregar al diagrama de implementación servicios/funciones, no tablas:

- Política `comprobar_acceso_estudio`.
- Vistas funcionales `pagina`, `catalogo`, `serie`, `contenido`, `eventos`.
- Servicio `solicitar / preparar / procesar_visor_uno` y análisis `cabecera / agrupar`.
- Adaptadores frontend `abrirModelo` y `abrirDicom`, con operaciones `reset`, `zoom`, `rotate`, `dispose` y `slice` cuando corresponde.

`Estudio`, `Archivo`, `Paciente`, `Usuario`, `Autorizacion` y `LogActividad` conservan sus campos. La relación con un renderizador o una caché temporal no introduce una FK ni requiere actualizar el DER.
