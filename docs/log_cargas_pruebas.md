# Log temporal de cargas

En `.env`, usar `CARGA_LOG_ENABLED=True` y reiniciar Django. Para apagarlo,
usar `CARGA_LOG_ENABLED=False` y reiniciar nuevamente. No requiere migraciones.

El archivo es `logs/cargas.log` dentro del proyecto. Se rota a los 5 MiB:
se conservan hasta tres copias anteriores (`.1`, `.2`, `.3`). Git ignora estos
archivos. Guardarlos en un lugar privado si se necesitan para investigar.
Después de detener Django pueden borrarse exclusivamente esos cuatro archivos.

Registra fecha/hora local del servidor, etapa, IDs internos, bytes, cantidad de
partes y duración de operaciones del backend. En errores conserva tipo de
excepción y ubicación en el código, pero no el mensaje de la excepción, rutas
de archivos médicos, nombres de pacientes, DNI, credenciales ni URLs firmadas.
La auditoría funcional existente es independiente y no cambia.

Para una incidencia: anotar hora, ID de importación y paso visible en pantalla;
conservar el log y describir qué ocurrió. No enviar los estudios ni datos del
paciente por canales públicos.

Las partes se suben directamente desde el navegador a S3/MinIO: Django no ve
cada byte ni cada corte de red. Este log registra la habilitación de la subida
y su verificación final, no un progreso de transferencia. Si falta el evento
`archivo_completo`, investigar navegador y almacenamiento; por sí solo no
prueba la causa. Las duraciones registradas corresponden al backend, no al
tiempo total de subida por Internet.

`parser_dicom_error` y `parser_gwg16_error` indican fallback controlado:
puede continuar la confirmación manual sin metadatos completos. No significa
que el archivo médico se haya perdido. `analisis_error` significa que el análisis
no terminó. `deteccion_desconocido` indica formato no reconocido.

Los mensajes de consola preexistentes de Django/boto3 no forman parte de este
archivo sanitizado: revisarlos antes de compartirlos. Usar un solo proceso Django
para estas pruebas; la rotación estándar no coordina múltiples workers.
