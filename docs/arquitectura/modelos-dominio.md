# Modelos del dominio

Los modelos de SISETMA están implementados mediante el ORM de Django y se
distribuyen por responsabilidad funcional. Cada clase incluye una explicación
breve en su propio archivo `models.py`.

- `usuarios`: contiene `Usuario`, cuenta autenticable con rol, y `Odontologo`,
  perfil profesional del derivante.
- `pacientes`: contiene `Paciente`. El registro clínico puede existir sin una
  cuenta web; la relación con `Usuario` es opcional.
- `estudios`: contiene `Estudio`, asociado obligatoriamente a un paciente.
- `archivos`: contiene `Archivo`, con metadatos, integridad y reemplazos.
- `accesos`: contiene `Autorizacion`, que habilita o revoca el acceso de un
  odontólogo a un estudio.
- `auditoria`: contiene `LogActividad`, registro de visualizaciones, descargas,
  publicaciones, correcciones, revocaciones y eliminaciones.
- `core`: centraliza los roles, estados, formatos y tipos de evento.

Las migraciones iniciales representan estas clases y sus relaciones. Cualquier
cambio posterior en el DER deberá reflejarse primero en la documentación y
luego en los modelos y migraciones.
