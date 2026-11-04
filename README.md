# AgentOps Tareas

Dos agentes academicos sobre un gestor de tareas Python 3.13 / FastAPI / PostgreSQL:

- WhatsApp → solicitud duradera → aclaracion o propuesta de IA → Docker aislado →
  PR → controles y proteccion de main → integracion → Render → confirmacion por WhatsApp.
- Push a una rama de desarrollo → Ruff, mypy, pytest y Chromium → revision contextual
  → PR valido o correctivo → los mismos controles de integracion y despliegue.

Aplicacion: [AgentOps Tareas](https://agentops-tasks.onrender.com/).
Usar datos ficticios: la lista es compartida y no tiene login.

## Estado y puesta en marcha

El CRUD y el intercambio real de mensajes estan comprobados. Los agentes estan
implementados y tienen pruebas locales; la demostracion completa en la nube se
registra por separado en [progreso](docs/progreso.md) y [evidencias](docs/evidencias.md).
Una prueba con proveedores simulados no acredita un despliegue real.

Seguir [activacion final y despliegue](docs/activacion-final.md). Incluye variables
por servicio, proteccion de main, token de WhatsApp y pruebas del participante.
El agente no puede modificar workflows, dependencias, migraciones ni evaluaciones.

## Instalacion local

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
$env:SERVICE_ROLE = 'tasks'
# Configurar DATABASE_URL en privado con una base de desarrollo.
.venv/Scripts/python -m bootstrap.serve
```

El servidor no carga .env automaticamente. [.env.example](.env.example) documenta
variables; nunca subir valores privados. Las migraciones versionadas se aplican
al arrancar, con transaccion, checksum y advisory lock.

## Validacion reproducible

```powershell
.venv/Scripts/python -m ruff check bootstrap harness taskapp tests
.venv/Scripts/python -m ruff format --check bootstrap harness taskapp tests
$sha = git rev-parse HEAD
docker build --file Dockerfile.validation --tag "agentops-validator:$sha" .
.venv/Scripts/python -m harness.sandbox --image "agentops-validator:$sha"
```

El contenedor tiene PostgreSQL de prueba, Chromium y dependencias preinstaladas.
Ejecuta lint, formato, tipos, pytest y cobertura >=80%, sin red externa, secretos,
privilegios ni escritura en la raiz. Las pruebas de referencia son inmutables.
Los benchmarks de IA se activan aparte; [matriz de validacion](docs/validacion-final.md).

## Documentacion

- [Arquitectura y defensa academica](docs/defensa.md).
- [Guion de demostracion](docs/demo.md).
- [Convenciones Python](docs/convenciones-python.md).
- [Arnes y limites](docs/arnes.md), [aislamiento](docs/validacion-aislada.md).
- [Solicitudes y estados](docs/solicitudes-reales.md), [revision de pushes](docs/revisor.md).
- [Diagnostico de WhatsApp](docs/diagnostico-whatsapp.md), [privacidad](docs/privacidad.md).

Los servicios gratuitos pueden suspenderse por inactividad y las cuotas de IA son
limitadas. No se activa facturacion. Un fallo detiene el trabajo y conserva evidencia;
el estado succeeded exige comprobar el commit publicado, salud y acceso a PostgreSQL.
