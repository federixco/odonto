# Paginación, recursos e identidad del lote

## Implementado en `fix/errores-criticos`

- Listados de pacientes, odontólogos, estudios planos/agrupados y tableros:
  **25 elementos por página**, con orden estable y filtros conservados en los
  enlaces. Las agrupaciones respetan también el filtro de estado.
- Explorador administrativo y de consulta: **100 archivos por página**. El árbol
  se construye solo con esa página. El contador general conserva el total del
  estudio y la descarga ZIP sigue incluyendo todos los archivos vigentes.
  Las cantidades/tamaños de cada carpeta dibujada corresponden a la página.
- Las opciones de reemplazo se limitan a los archivos incorrectos de esa página;
  para corregir otro archivo se navega a su página.
- Los tableros usan conteos SQL de archivos disponibles, en lugar de precargar
  todo el volumen. El derivante recibe como máximo cuatro archivos de resumen
  por estudio; el paciente solo necesita el conteo. La ficha del paciente también
  usa un conteo SQL de estudios, sin precargar la relación completa.
- El análisis recorre todas las fuentes clínicas reconocibles, no los primeros
  25 archivos. Lee hasta **256 KiB** de cabecera por DICOM ordinario, **8 MiB** por
  DICOMDIR y **2 MiB** por GWG. En archivos desconocidos primero lee 132 bytes
  para identificar la firma DICM. No necesita leer los píxeles del volumen.
- Se reutiliza un cliente S3 dentro del análisis, cerrando sus respuestas. No se
  cachean globalmente credenciales ni clientes entre análisis. Los cambios de
  formato/serie se escriben por lotes de hasta 500 filas.
- Las referencias de serie de DICOMDIR se asocian por ruta exacta, relativa al
  propio índice, no por un recorrido cuadrático de sufijos. Una ruta ambigua no
  recibe arbitrariamente el UID de una serie.
- Las lecturas S3 ya no ocurren dentro de la transacción que guarda el resultado
  final del análisis y cambia su estado.

## Detección de pacientes mezclados

Se comparan identificador, nombre normalizado y fecha de nacimiento en las
cabeceras DICOM, los registros PATIENT de DICOMDIR y los PatientInfo de GWG16.
También se comparan fuentes de formatos diferentes dentro del mismo lote.
Mayúsculas, separadores DICOM y acentos no crean diferencias por sí solos.

Si aparecen valores incompatibles, el resultado se marca **mezclado**, se retira
la sugerencia de paciente y la pantalla pide separar las carpetas. No se permite
crear una ficha desde ese lote ni confirmarlo seleccionando manualmente un
paciente. El bloqueo existe en las vistas y en el método de confirmación del
modelo, sin agregar columnas ni migraciones.

El resultado guarda códigos/cantidades, no un listado adicional de nombres o
documentos de todos los pacientes. Los logs técnicos no incluyen esas identidades.

Esta comparación es conservadora: errores de escritura o datos incompatibles de
una misma persona también requieren revisar/separar la exportación. No se intenta
decidir clínicamente cuál dato es correcto ni dividir un paquete automáticamente.

### Límites explícitos

- Sin identificador, con datos incompletos o con cabeceras no legibles, el resultado
  es parcial o no verificable. Se advierte al operador; no se presenta como garantía
  de paciente único. Un DICOMDIR mayor que el límite se considera revisión parcial.
- Imágenes, PDF y modelos sin datos clínicos estructurados no permiten detectar por
  sí solos a qué paciente pertenecen. Su presencia genera una advertencia de
  verificación parcial, igual que auxiliares de formato desconocido; no bloquea
  por sí sola la carga. Se mantiene la selección/revisión manual.
- No se reanalizan ni se reparan automáticamente importaciones ya confirmadas.
- Revisar todo el lote puede tardar más que inspeccionar solo el primer archivo.
  Se limita la lectura y la memoria y se reutilizan conexiones, pero no se ha medido
  aún el tiempo real con exportaciones grandes. No se promete una capacidad de VPS.

## Verificación y pruebas pendientes

Se comprobó la sintaxis Python y la compilación de las plantillas, sin conectarse
a una base de datos. Las pruebas funcionales siguen diferidas, como se acordó.
No se inició MySQL ni MinIO, no se borraron datos y no se hizo commit o push.

Casos preparados: mezcla al final de una carpeta de más de 25 archivos, varios
pacientes en DICOMDIR/GWG, coincidencias normalizadas, límites de página, filtro
de estado, árbol acotado y reutilización/cierre del cliente S3.

Con MySQL iniciado, desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe manage.py test apps.estudios.tests.test_lotes_mezclados apps.estudios.tests.test_paginacion_recursos apps.estudios.tests.test_importador apps.archivos.tests.test_storage --settings=config.settings.test_mysql
```

Luego ejecutar la suite completa con esa misma configuración MySQL aislada.
Comprobar con una exportación real grande los tiempos y los límites de cabecera,
y recorrer los enlaces de paginación en los tres roles.

## Lo que queda fuera de este bloque

Cancelación/reintentos y concurrencia se reservan para el siguiente bloque.
Tampoco se implementan todavía búsquedas remotas/paginadas para todos los
selectores de pacientes y odontólogos, trabajos de hash/análisis en segundo
plano ni una política diferente de verificación del bucket por carga.
El SHA-256 sigue leyéndose por bloques y mantiene su costo de recorrer el objeto
completo: no se sacrificó la comprobación de integridad para ganar velocidad.
