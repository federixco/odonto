# Estructura modular de SISETMA

```text
sisetma/
|-- config/                 Configuración global y entradas del servidor
|   `-- settings/           Ajustes separados por entorno
|-- apps/                   Módulos de negocio Django
|   |-- core/               Componentes compartidos mínimos
|   |-- usuarios/           Cuentas y autenticación
|   |-- pacientes/          Fichas identificatorias de pacientes
|   |-- estudios/           Ciclo de vida de los estudios
|   |-- archivos/           Carga, validación y descarga de archivos
|   |-- accesos/            Autorizaciones y revocaciones
|   |-- auditoria/          Trazabilidad de acciones
|   `-- notificaciones/     Avisos por correo
|-- integraciones/          Adaptadores de infraestructura
|   |-- almacenamiento/     Disco local o servicio compatible con S3
|   |-- dicom/              Orthanc y DICOMweb
|   `-- correo/             Proveedor de correo
|-- templates/              Plantillas HTML compartidas
|-- static/                 CSS, JavaScript e imágenes propias
|-- media/                  Archivos locales solo durante desarrollo
|-- tests/                  Pruebas integrales entre módulos
|-- docs/                   Documentación técnica
|-- logs/                   Registros locales ignorados por Git
|-- manage.py               Comandos de Django
|-- .env.example            Variables esperadas, sin secretos reales
`-- README.md               Presentación del repositorio
```

## Criterios

- Es un monolito modular: se despliega una sola aplicación, pero el código se divide por responsabilidades del negocio.
- `pacientes` separa la ficha de una persona de su cuenta opcional en `usuarios`.
- `archivos` administra metadatos y reglas; los archivos binarios vivirán fuera de MySQL.
- `integraciones` aísla tecnologías reemplazables como S3, Orthanc y el proveedor de correo.
- Cada módulo tendrá sus propias migraciones, plantillas y pruebas.
- Las reglas sensibles de autorización se centralizarán en `accesos` y deberán tener pruebas automáticas.

## Archivos que se agregarán al comenzar el desarrollo

Cuando se inicialicen formalmente las aplicaciones Django, cada módulo incorporará solo lo que necesite, por ejemplo:

```text
models.py       Entidades persistentes
admin.py        Administración interna de Django
forms.py        Formularios HTML
urls.py         Rutas propias del módulo
views.py        Controladores de las pantallas
services.py     Casos de uso y operaciones con escritura
selectors.py    Consultas de lectura reutilizables
tasks.py        Tareas en segundo plano, cuando se incorpore Celery
```

No se crean todos esos archivos vacíos desde el principio para evitar estructura sin utilidad real.

