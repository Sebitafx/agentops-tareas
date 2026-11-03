# Gestor de tareas y despliegue del segundo servicio

La interfaz y API estan en taskapp/. PostgreSQL usa agentops_tasks, creada por la
migracion aditiva 002_tasks.sql. La migracion conserva las tablas y mensajes de WhatsApp.
Una sola imagen ofrece dos roles en dos servicios separados: receiver y tasks.
Sin SERVICE_ROLE se mantiene receiver por compatibilidad con el primer despliegue.

## Desplegar

1. Esperar CI aprobada y redesplegar agentops-receiver al nuevo commit: aplicara la
   migracion aditiva y actualizara las paginas de privacidad que usa Meta.
2. Crear otro Web Service en Render con el mismo repositorio y rama main.
3. Nombre agentops-tasks; Docker; Oregon; plan Free; raiz vacia; Dockerfile ./Dockerfile.
4. Variables: SERVICE_ROLE=tasks y DATABASE_URL con la misma conexion privada de Neon.
   Este servicio no necesita META_APP_SECRET ni claves de IA o de GitHub App.
5. Health check /health; Auto-Deploy Off; no sobrescribir Docker Command ni pre-deploy.
6. Desplegar y comprobar /version y /ready. Abrir / y recorrer crear, editar, completar,
   filtrar, recargar y eliminar una tarea ficticia. Registrar URL y commit como evidencia.

Los dos servicios comparten la cuota gratuita de Render. Se mantiene el alcance de
demo, sin login ni datos reales. La lista es publica y cualquier visitante puede
modificarla. No publicar tareas sensibles ni capturas con datos personales.

## Contrato HTTP

| Operacion | Contrato |
|---|---|
| GET /api/tasks | Lista todas. status=all,pending,completed filtra en PostgreSQL. |
| POST /api/tasks | title y description opcional. Devuelve 201 y tarea pendiente. |
| GET /api/tasks/{id} | Tarea o 404. UUID invalido: 422. |
| PATCH /api/tasks/{id} | title, description y/o completed; conserva campos omitidos. |
| DELETE /api/tasks/{id} | 204 sin cuerpo; 404 si no existe. |

Respuesta: id UUID, title, description, completed booleano y timestamps UTC
created_at/updated_at. Titulo sin espacios extremos, entre 1 y 200 caracteres;
descripcion hasta 4000, se puede vaciar. No se aceptan claves extra, patch vacio
ni null. Orden por creacion descendente e id para desempatar.

Sin DB, /health sigue activo; /ready y operaciones de tareas dan 503. Los errores
del driver se ocultan al cliente y los logs no incluyen la conexion. La UI conserva
datos del formulario ante errores y permite reintentar. El contenido de tareas se
inserta con textContent, sin interpretar HTML.

## Validacion y E2E

Ruff valida bootstrap, harness, taskapp y tests. Mypy comprueba taskapp, que sera
la superficie editable del agente. Pytest combina receptor, proveedores y CRUD con
PostgreSQL de prueba. Chromium recorre el flujo real, persistencia al recargar,
filtros, eliminacion, HTML mostrado como texto y anchura de pantalla movil.

Para ejecutar E2E local, instalar dependencias dev y Chromium con
python -m playwright install chromium; definir TEST_DATABASE_URL para una base
aislada llamada agentops_test, y E2E_ENABLED=1. Las capturas quedan en artifacts/.
Nunca usar la base de demostracion para la suite: los fixtures limpian tablas de prueba.

El gestor aun no dispara agentes: sera el proyecto al que estos propondran cambios.
