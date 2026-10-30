# AgentOps Tareas

Dos retos academicos: solicitudes por WhatsApp que generan cambios y despliegues,
y revision y correccion de Python tras cada push.

## Estado real

Primera etapa: servicio minimo para comprobar infraestructura. Meta ya envio un
mensaje al participante autorizado y recibio su respuesta en su propio panel.
La conexion entre Meta y este servidor aun no esta validada.

Implementado: salud, version del commit, handshake del webhook y pruebas.
Pendiente: PostgreSQL, recepcion duradera, gestor de tareas, agentes, PR automaticos
y despliegue validado por CI. No es todavia la entrega final de ninguno de los retos.

## Ejecutar localmente (PowerShell)

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
$env:META_VERIFY_TOKEN = 'elige-un-valor-privado'
.venv/Scripts/python -m uvicorn bootstrap.main:app --port 8000
```

Las variables de `.env.example` documentan la configuracion; el servidor no carga
archivos `.env` automaticamente. Configurar variables en la consola o en Render.
Nunca compartir tokens, archivos `.env` ni claves privadas en el repositorio.

## Validacion

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check bootstrap tests
.venv/Scripts/python -m ruff format --check bootstrap tests
```

## Publicar el servicio minimo en Render

1. Crear una cuenta en Render o iniciar sesion con GitHub.
2. Crear un **Web Service**, conectar este repositorio y seleccionar `main`.
3. Elegir runtime **Docker**, plan **Free** y health check `/health`.
4. Configurar `META_VERIFY_TOKEN` con un valor privado elegido por ti. Es un token
   de verificacion propio, distinto del token de acceso generado por Meta.
5. Desactivar Auto-Deploy: los despliegues de esta etapa son manuales. Los
   despliegues automaticos controlados por el pipeline se implementaran despues.
6. Desplegar y verificar `/health` y `/version` en la URL de Render.
7. En Meta, la URL de callback sera `https://TU-SERVICIO.onrender.com/webhooks/whatsapp`.
   Usar exactamente el mismo `META_VERIFY_TOKEN` para verificar el callback.

`/ready` devuelve **503** intencionalmente: el sistema aun no tiene almacenamiento
ni agentes. Los POST del webhook tambien devuelven **503**, evitando confirmar y
perder mensajes. No suscribir mensajes reales hasta implementar su persistencia.
Un handshake exitoso solo prueba el GET de verificacion, no la recepcion completa.

Render Free puede suspender el servicio por inactividad. No agregar metodo de pago
ni cambiar de plan para esta demo sin revisar primero sus condiciones y cuotas.

## Proximas etapas

1. Conectar Neon, migraciones y bandeja duradera de mensajes con firma y deduplicacion.
2. Validar recepcion real y respuesta desde nuestro servidor por WhatsApp.
3. Construir CRUD, filtros y pruebas de la aplicacion de tareas.
4. Habilitar Gemini y GitHub App, arnes, revision y correcciones aisladas.
5. Proteger main, automatizar integracion y despliegue con comprobacion del SHA.
6. Ejecutar los dos recorridos reales y preparar evidencias y defensa.
