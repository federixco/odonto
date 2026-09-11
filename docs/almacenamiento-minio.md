# Almacenamiento de estudios con MinIO/S3

La Etapa 3 utiliza cargas multipartes directas desde el navegador. Django autoriza
la operación y conserva los metadatos; los bytes del estudio viajan directamente
al bucket privado.

## Preparación local

1. Ejecutar una instancia local de MinIO.
2. Crear un bucket privado llamado `sisetma-estudios`.
3. Copiar las variables S3 de `.env.example` al `.env` local y reemplazar las
   credenciales de ejemplo por las de esa instalación.
4. Configurar CORS en el bucket para permitir `PUT` desde
   `http://127.0.0.1:8000` y `http://localhost:8000`.
5. Exponer el encabezado `ETag`; el navegador lo necesita para completar cada
   carga multipartes.
6. Permitir los encabezados usados por las URLs prefirmadas y limitar los métodos
   del bucket a los estrictamente necesarios.
7. Configurar una regla que aborte cargas multipartes incompletas y antiguas. Esa
   regla no debe eliminar estudios completados, cuya conservación es indefinida.

El bucket no debe ser público. Las claves y secretos de MinIO o AWS nunca se
incluyen en Git ni se envían al navegador.

## Flujo implementado

1. El administrador crea un estudio en estado `BORRADOR`.
2. Django valida nombre, extensión y tamaño del archivo.
3. Django inicia la carga en S3/MinIO y devuelve URLs prefirmadas temporales.
4. JavaScript divide el archivo en partes y las envía directamente al bucket.
5. Django solicita a S3 que ensamble el objeto, comprueba su tamaño y calcula un
   SHA-256 real mediante lectura por bloques.
6. Solo entonces el archivo cambia a `COMPLETO` y se registra la carga en la
   auditoría.

La comprobación SHA-256 actual se realiza de forma síncrona y sin cargar el objeto
completo en memoria. Si en producción la verificación demora demasiado, deberá
trasladarse a un proceso de fondo antes de habilitar la publicación.

## Pruebas

Las pruebas automatizadas simulan S3 y usan archivos pequeños. La prueba manual
con MinIO debe hacerse con archivos sintéticos, nunca con información real de
pacientes. Antes de aprobar el despliegue se debe verificar también cancelación,
reintentos, límites de tamaño, CORS y recuperación de cargas abandonadas.
