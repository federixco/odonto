# MySQL local

Esta guía configura una base vacía y un usuario limitado al esquema de
SISETMA. No guardar la contraseña real en este repositorio ni en capturas de
pantalla.

## 1. Crear la base y el usuario

Ejecutar en MySQL con una cuenta administrativa. Reemplazar `CAMBIAR_ESTA_CLAVE`
por una contraseña local segura.

```sql
CREATE DATABASE sisetma
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER 'sisetma_app'@'localhost'
    IDENTIFIED BY 'CAMBIAR_ESTA_CLAVE';

GRANT ALL PRIVILEGES ON sisetma.* TO 'sisetma_app'@'localhost';
FLUSH PRIVILEGES;
```

El usuario queda limitado a `sisetma.*`; no se le conceden privilegios
globales ni administración de otros esquemas. En el entorno local necesita
permisos de creación y modificación porque ejecuta las migraciones de Django.

## 2. Configurar el entorno

Desde la raíz del proyecto:

```powershell
Copy-Item .env.example .env
```

Editar `.env` y dejar la sección de base de datos así, usando la contraseña
real únicamente en ese archivo:

```dotenv
DB_ENGINE=django.db.backends.mysql
DB_NAME=sisetma
DB_USER=sisetma_app
DB_PASSWORD=la-clave-local
DB_HOST=localhost
DB_PORT=3306
```

La aplicación carga `.env` si existe, pero nunca reemplaza una variable de
entorno ya exportada. Esto permite que CI y producción inyecten sus secretos
sin depender de archivos locales.

## 3. Verificar la conexión

Con el entorno virtual activo y MySQL ejecutándose:

```powershell
python manage.py check --database default
python -c "from django.db import connection; connection.ensure_connection(); print(f'Conectado a {connection.vendor}')"
python manage.py migrate
```

La segunda orden comprueba una conexión real sin imprimir credenciales. Las
migraciones se ejecutan sobre la base vacía y su implementación se mantiene
como una tarea separada del modelado de dominio.
