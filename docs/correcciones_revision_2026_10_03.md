# Correcciones de la revisión de código del 29/09

Fecha: 3 de octubre de 2026. Rama: `fix/errores-criticos`.

## Alcance implementado

- **H06:** se retiraron los imports locales de `messages` que causaban un
  `UnboundLocalError` cuando la importación ya tenía paciente seleccionado.
- **H07:** detectar DICOM ya no reclasifica todos los archivos del lote. PDF,
  imágenes y modelos conservan su formato. Los archivos de formato desconocido
  se clasifican como DICOM únicamente si su cabecera contiene la firma DICM;
  para esta comprobación se solicitan 132 bytes por objeto.
- **H09 y R06:** ambas variantes de confirmación usan el mismo selector de
  pacientes. Se implementó búsqueda por nombre, apellido y DNI, sin distinguir
  acentos ni mayúsculas, con selección visible y aviso cuando no hay resultados.
  La selección y sus errores se conservan al volver a mostrar el formulario.
- **H10:** el diálogo de coincidencia de DNI usa `textContent`, no `innerHTML`,
  para mostrar nombres no confiables. El DNI se compara exactamente, como en
  el backend, y se vuelve a comprobar al aceptar la asociación.
- **H11:** el botón ZIP está fuera del árbol recursivo. Aparece aunque el árbol
  se reduzca a una sola carpeta, no se duplica y no se ofrece cuando el estudio
  está eliminado o no tiene archivos completos.
- **H12:** un reemplazo conserva la carpeta del original y utiliza el nombre
  del nuevo archivo. Se rechazan rutas demasiado largas y colisiones con
  archivos completos o en carga, incluida una colisión en la raíz con un archivo
  sin ruta explícita. El reemplazo no copia la FK de importación: mantiene la
  relación `archivo_reemplazado`, evitando duplicar la ruta única del histórico.
- **C05:** cambiar la vista solo modifica sus cuatro clases permitidas. No
  borra `folder-root` ni otras clases del panel. Una preferencia inválida o el
  bloqueo de `localStorage` no impiden usar el explorador.
- **E02:** si falla la limpieza remota tras una verificación fallida, el archivo
  igualmente queda `INCORRECTO` y se devuelve el error previsto. Si el aborto de
  un multipart no se confirma, se conserva su identificador para reconciliarlo.
- **E03:** el endpoint antiguo de corrección rechaza archivos que todavía no
  tienen estudio asociado, en lugar de fallar con un error interno.

## Política de reemplazos y límites

Si se reemplaza `exportacion/informes/informe.pdf` con `corregido.pdf`, la nueva
ruta es `exportacion/informes/corregido.pdf`. Si se conserva el nombre, se
conserva la ruta completa. Cuando un visor externo depende de nombres exactos,
es necesario mantener esos nombres: esta corrección no reescribe referencias
dentro de DICOMDIR ni dentro de paquetes propietarios.

No se modifica el esquema, no se agregan migraciones y no se reparan
automáticamente metadatos de importaciones ya confirmadas. Tampoco se ejecutan
borrados, limpiezas de MinIO, commits o pushes.

## Comprobaciones realizadas

- Sintaxis de siete archivos Python modificados/nuevos.
- Compilación de ocho plantillas sin conectar una base de datos.
- Comprobación de sintaxis de `paciente_selector.js` y `file_view.js` con Node.
- Revisión de diferencias y espacios en blanco con Git.

El chequeo general de Django no pudo completarse porque MySQL estaba detenido.
Por indicación del usuario, **las pruebas funcionales y de regresión quedaron
para después**. Estas comprobaciones no equivalen a probar la aplicación en
el navegador ni con archivos reales.

## Pruebas preparadas para después

Se agregaron 21 casos: 15 en `apps/estudios/tests/test_revision_pendientes.py`,
cinco en `apps/archivos/tests/test_rutas_reemplazo.py` y uno en
`apps/estudios/tests/test_importador.py`. Simulan S3; no requieren vaciar MinIO
ni modificar datos reales.

Con MySQL iniciado, desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe manage.py test apps.estudios.tests.test_revision_pendientes apps.estudios.tests.test_importador apps.archivos.tests.test_rutas_reemplazo --settings=config.settings.test_mysql
```

Para ejecutar luego la suite completa:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.settings.test_mysql
```

La configuración utiliza las credenciales MySQL de `.env` y una base temporal
con nombre aleatorio `test_odonto_revision_...`, creada y eliminada por Django.
El usuario de MySQL debe tener permisos para crearla. No usar `--keepdb` con
esta configuración, porque cada ejecución elige otro nombre.

También queda por verificar manualmente:

1. Buscar y cambiar paciente en ambas variantes de confirmación; probar nombres
   con acentos y una búsqueda sin resultados.
2. Introducir un DNI ya registrado, cancelar el diálogo y luego aceptar; comprobar
   que no se crea una ficha duplicada y que se muestran los errores del formulario.
3. Importar una carpeta DICOM mixta y comprobar que PDF e imágenes todavía ofrecen
   previsualización. Probar nombres con caracteres especiales usando datos ficticios.
4. Cambiar las cuatro vistas y recargar. La estructura del explorador debe mantenerse.
5. Reemplazar un archivo y descargar el ZIP para comprobar su carpeta, nombre e
   histórico. Verificar también un estudio con una sola carpeta.

## Pendientes del informe

Actualización: el siguiente bloque implementó paginación de listados/exploradores,
resúmenes acotados y detección de identidades mezcladas. Su alcance y límites están
en `docs/paginacion_y_validacion_lotes_2026_10_03.md`. Las pruebas siguen pendientes.

Este bloque no cierra toda la revisión. Quedan las mejoras de paginación y
consumo de recursos, el ciclo completo de cancelación/reintentos, la concurrencia
de otras operaciones, la detección de pacientes mezclados en un lote, la limpieza
conservadora de código huérfano, otras duplicaciones/CSS y el endurecimiento de
producción. La corrección E02 no resuelve por sí sola E01 en la carga individual.
La clasificación por firma tampoco sustituye una validación clínica de los datos.
