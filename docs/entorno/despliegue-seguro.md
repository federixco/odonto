# Seguridad del despliegue D.O.C.

Estas barreras preparan el código para un VPS Linux con Django y MySQL juntos,
y almacenamiento de objetos externo. No configuran el VPS ni los permisos
del proveedor, y no reemplazan una auditoría de seguridad antes de publicar.

## Base de datos dentro del VPS

En producción se exige MySQL y una cuenta distinta de `root`, con contraseña.
`DB_SOCKET` debe indicar el archivo de socket real del servidor, por ejemplo
`/run/mysqld/mysqld.sock`. Django lo utiliza como `HOST` y deja `PORT` vacío.
La comunicación ocurre localmente por el sistema operativo, no por Internet.
Esto no cifra la base de datos ni impide accesos si el VPS queda comprometido.

El administrador del VPS debe verificar la ruta y los permisos del socket,
cerrar los puertos de MySQL al exterior (incluido X Protocol si está activo)
y desactivar interfaces de red innecesarias. Usar una cuenta de aplicación
limitada a su base de datos. Para la ejecución habitual bastan permisos de
lectura/escritura; ejecutar migraciones con una cuenta de despliegue que tenga
los permisos de esquema necesarios, no concederlos permanentemente al proceso web.

Windows local conserva TCP y MinIO HTTP: dejar `DB_SOCKET` vacío en desarrollo.
No se cambió el `.env` existente ni la base de datos.

## Configuración de producción

Ejemplo orientativo, **no listo para copiar y publicar**: sustituir dominios,
rutas, credenciales y secretos por valores reales. Mantener el archivo fuera
de Git y del directorio servido por el servidor web, con permisos restringidos.

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=REEMPLAZAR_POR_UN_SECRETO_ALEATORIO_DE_AL_MENOS_50_CARACTERES
DJANGO_ALLOWED_HOSTS=doc.example.org
DJANGO_SECURE_SSL_REDIRECT=True
DB_ENGINE=django.db.backends.mysql
DB_NAME=sisetma
DB_USER=sisetma_app
DB_PASSWORD=REEMPLAZAR
DB_SOCKET=/run/mysqld/mysqld.sock
AWS_ACCESS_KEY_ID=REEMPLAZAR
AWS_SECRET_ACCESS_KEY=REEMPLAZAR
AWS_STORAGE_BUCKET_NAME=REEMPLAZAR
AWS_S3_ENDPOINT_URL=https://storage.example.invalid
AWS_S3_UPLOAD_EXPIRATION=3600
AWS_S3_DOWNLOAD_EXPIRATION=300
AWS_S3_PREVIEW_EXPIRATION=900
```

Sin endpoint personalizado, boto3 utiliza el endpoint oficial de AWS.
Producción rechaza SQLite, variables obligatorias vacías, `root`, sockets
inválidos, endpoints HTTP o con credenciales en la URL, y desactivar la
redirección HTTPS. Estos controles no verifican los privilegios reales de
la cuenta MySQL ni que las claves S3 sean válidas o estén limitadas.

## HTTPS y almacenamiento privado

Configurar Caddy/Nginx con certificado HTTPS válido. El proceso Django solo
debe recibir tráfico del proxy autorizado; este debe sobrescribir
`X-Forwarded-Proto`, sin confiar en el encabezado enviado por el visitante.
No exponer el servidor de desarrollo al público. La configuración de
producción mantiene cookies seguras y `DEBUG=False`.

Las conexiones boto3 verifican certificados (`verify=True`). Los endpoints
externos de producción deben ser HTTPS. Las claves secretas permanecen en
el backend. Configurar el bucket privado y sus credenciales con permisos
limitados al bucket y a las operaciones necesarias; no utilizar claves de
administración del proveedor.

Para comprobar que un archivo existente y el listado rechazan acceso anónimo:

```bash
python manage.py verificar_almacenamiento_privado --archivo-id ID_REAL --settings=config.settings.production
```

El comando verifica primero que la cuenta autenticada pueda acceder al bucket
y al objeto, y luego exige denegación HTTP 403 para listado y lectura anónima.
No crea ni borra objetos. No se ejecuta automáticamente al iniciar el sistema.
Un error de conexión o un 404 no se considera prueba de privacidad.
Verifica **un objeto de muestra**, no todas las políticas/objetos: revisar
también permisos públicos y configuraciones específicas en el proveedor.

## Permisos temporales y registro de errores

Las URLs prefirmadas vencen, por defecto, a los 60 minutos para las partes
de subida, 5 minutos para iniciar descargas y 15 minutos para previsualizar.
Se generan tras las comprobaciones de acceso existentes. Volver a ingresar
al sistema permite solicitar una URL nueva si el permiso sigue vigente.
Una URL ya emitida puede seguir funcionando hasta su vencimiento aunque se
revoque el permiso en la aplicación: no es revocación instantánea en S3.
La variable histórica `AWS_S3_PRESIGNED_EXPIRATION` queda como fallback solo
para subidas. Verificar los tiempos con la conexión real del centro antes
de producción; no se agregó renovación automática de partes aquí.

En los errores controlados de carga/análisis/ZIP se registran mensajes
genéricos e identificadores internos, sin el mensaje completo del proveedor
ni su traceback. El registro temporal de carga conserva tipo de error y
ubicación del código, sin datos del paciente ni URLs. No habilitar logs DEBUG
de boto3/botocore en producción. Esto no constituye una revisión exhaustiva
de todos los registros del servidor/proxy y del proveedor.

## Pruebas aisladas

```powershell
.venv\Scripts\python.exe manage.py test apps.core.tests.test_config_segura apps.archivos.tests.test_storage apps.archivos.tests.test_privacidad_storage apps.core.tests.test_carga_log --settings=config.settings.test
```

Este subconjunto usa SQLite temporal y bloquea transporte S3 real. Verifica
configuración, certificados, vencimientos, privacidad simulada y registro
de errores sin secretos.

La suite completa necesita MySQL para probar los bloqueos de concurrencia:

```powershell
.venv\Scripts\python.exe manage.py test --settings=config.settings.test_mysql --noinput
```

Se crea una base `test_odonto_revision_...` con nombre independiente y se
elimina al terminar; no se prueban operaciones sobre la base `sisetma`.
La cuenta local debe tener permisos para crear/eliminar esa base temporal.
S3 sigue simulado. Incluye acceso ajeno/revocado, carga y ZIP; no reemplaza
una prueba con el proveedor real ni una revisión del VPS de producción.
