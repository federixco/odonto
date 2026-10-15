# D.O.C. — landing institucional (15/10/2026)

## Alcance y dirección

Rediseño local de `/` en `fix/landing-page`. El usuario confirmó que la portada debe presentar el centro, sus profesionales e información, manteniendo visible el acceso a estudios. [Predim](https://predim.com.ar/) fue referencia de jerarquía institucional, no una plantilla ni una fuente de imágenes.

Extensión del mundo «claridad clínica», modo Persuade y semilla heredada `ceada702`. No se reemplazan PRODUCT.md, DESIGN.md ni sus decisiones globales. Contrato local de desarrollo: `.impeccable/surfaces/templates-core-landing-html.md`.

Archivos de implementación: `templates/core/landing.html`, `static/core/css/landing.css`, `static/core/fonts/Manrope-variable.ttf` y su licencia. Pruebas: `apps/core/tests/test_landing.py`.

## Decisiones implementadas

- Cabecera blanca sticky y acceso a estudios independiente del menú. Usuarios anónimos van a `login`; con sesión, a `redireccion_roles`. Los endpoints y permisos no cambian.
- Recorrido: presentación → estudios → centro/profesionales → acceso digital → contacto.
- Apertura clara con el equipo institucional Cone Beam. Se preservan servicios, nombres y contactos existentes. No hay retratos ficticios, credenciales inventadas, testimonios, cifras publicitarias ni horarios no confirmados.
- Profesionales destacados: Dra. María Luisa Stechina y Dr. Pedro Eduardo Morales.
- Contacto: Mitre 479, Formosa; 0370 442-2272, interno 2; doc.imagenes@gmail.com. Acciones reales de teléfono, correo y mapa externo.
- Portal separado de la presentación, con recuperación de contraseña y ayudas nativas. El autorregistro profesional sigue pendiente de habilitación por el centro; el paciente solicita una cuenta vinculada a sus estudios.
- Se reutilizan base pública, marca, iconos y JavaScript existentes. Las modificaciones visuales se limitan a `.landing-page` y clases exclusivas `landing-*`; no cambian login, administración, visores ni base de datos.

## Lenguaje visual local

Se mantiene el azul D.O.C. `#004b64`, superficies claras, turquesa y separadores finos. La landing incorpora Manrope local frente a Segoe UI del sistema operativo: texto base de 16px/1.7 y titular hasta 58px. El wordmark conserva su tratamiento existente.

Variantes locales: teal `#007c83`, ink `#153d49`, muted `#526a74`, line `#d5e3e7`, pale `#edf6f6`; botones de 8px de radio y bloques de 12–16px. No se promueven estas variantes a tokens globales. Botones sin salto ni sombra al pasar el cursor.

## Recursos

Se reutilizan sin edición de píxeles en esta tarea las imágenes existentes en `static/core/images/landing/`. La documentación previa atribuye su origen al material institucional `MARKETIN (1).pptx`:

- `doc-equipo-original.jpg`: `ppt/media/image6.jpeg`; encuadre mediante CSS.
- `doc-radiografias.jpg`: `ppt/media/image1.jpeg`.
- `doc-planificacion.png`: conversión preexistente de `ppt/media/image2.tiff`.

No son imágenes de Predim. Este cierre no certifica igualdad binaria con otras copias homónimas del repositorio ni reevalúa la adaptación vectorial previa del isotipo.

La nueva fuente proviene de [Google Fonts / Manrope](https://github.com/google/fonts/tree/main/ofl/manrope). Se sirve localmente, con preload, peso variable 200–800 y `font-display: swap`; no necesita solicitudes a Google durante la navegación. `Manrope-OFL.txt` conserva la SIL Open Font License 1.1 y la atribución The Manrope Project Authors.

## Responsive y accesibilidad

- Contenedor máximo 1220px; composición en dos columnas en escritorio.
- De 861 a 1120px se compactan marca, navegación y separaciones.
- Hasta 860px el menú es plegable con JavaScript y el botón de estudios ocupa una fila independiente. Sin JavaScript, la navegación permanece disponible.
- Hasta 620px las secciones se apilan. La dirección «Mitre 479 · Formosa» aparece antes del equipo, dentro de la primera pantalla móvil.
- Menú con `aria-expanded`, cierre con Escape y retorno de foco; ayudas `details/summary` nativas; foco visible y enlace para saltar al contenido.
- Movimiento reducido respetado; ningún contenido depende de una animación de entrada.

## Verificación

Comando reproducible sin SQLite:

```powershell
.\.venv\Scripts\python.exe manage.py test apps.core.tests.test_landing.LandingPublicaTests --settings=config.settings.test_mysql -v 1
```

Resultado: **9 pruebas aprobadas**, repetidas después de la corrección final. Son SimpleTestCase sin acceso a la base; verifican portada pública, recursos, profesionales/contacto, acceso fuera del menú, instrucciones de habilitación y protección de accesos existentes.

Playwright headless con Edge, en contexto aislado, verificó 1440, 1024, 861, 860, 768, 390 y 320px: sin overflow horizontal, imágenes faltantes, anclas inválidas, errores JS ni fallos del cálculo de contraste textual (logotipo exento). Manrope cargó correctamente. Se probaron menú, Escape/foco, ayudas por teclado, CTA visible, navegación sin JavaScript y movimiento reducido. GET anónimo del login conservó su clase `access-page` y formulario.

Capturas de hero y página completa a 1440 y 390px y JSON de resultados quedan en `.impeccable/review/landing-refresh/` (evidencia local ignorada por Git). Se recapturaron tras adelantar la dirección móvil y se repitieron las verificaciones.

Revisión independiente: inicialmente `fix` por dirección fuera del primer viewport móvil; corrección implementada y recapturada. Veredicto final **`ship`**, con el único hallazgo puntuado **resuelto** y sin fixes obligatorios pendientes. El veredicto de cierre revisó las cuatro capturas y se limita a ese hallazgo; no se presenta como nueva auditoría completa ni como aprobación del usuario.

El cargador y el detector de impeccable fallaron con `cache_directory_failed`; se usaron lectura directa del contexto, comprobaciones del navegador y revisión independiente. El detector no se contabiliza como validación aprobada. Los roles especializados no estaban disponibles como tipos de agente: se utilizaron agentes independientes equivalentes de revisión y documentación.

### Límites

No es una auditoría WCAG completa ni una prueba clínica de extremo a extremo. MySQL estaba detenido: se usó una vista previa WSGI de la portada con settings reales de desarrollo y estáticos, sin ejecutar checks de arranque que requieren conexión. No se modificaron servicios, datos, migraciones ni configuración para sustituir MySQL. No se verificaron autenticación real, envío de correo, MinIO ni permisos clínicos con usuarios reales.

## Documentación histórica preservada

La documentación v3 del 5 de octubre describe otra composición (hero azul y Segoe UI); sus capturas y pruebas no certifican este rediseño. DESIGN.md conserva el sistema clínico y sus pendientes. La tipografía Manrope y radios se documentan aquí como diferencias locales, sin corregir ese historial ni otros desajustes preexistentes. La referencia histórica a `.impeccable/design.json` no se repara como efecto secundario.
