# AgentOps Tareas

Dos retos academicos: solicitudes por WhatsApp que generan cambios y despliegues,
y revision y correccion de Python tras cada push.

## Estado real

Recorrido real WhatsApp -> Meta -> Render -> PostgreSQL verificado: un mensaje del
participante autorizado quedo guardado en Neon y confirmado en los logs del receptor.
El callback HTTPS, el campo messages y la suscripcion de la app a la WABA estan configurados.

Implementado: salud, version, handshake, migracion PostgreSQL y bandeja duradera
de mensajes con firma HMAC, lista de remitentes autorizados y deduplicacion.
Probado con PostgreSQL local y conexion real con Neon verificada desde `/ready`.
Pendiente: gestor de tareas, agentes, respuestas WhatsApp, PR automaticos y despliegue
autonomo. Guardar un mensaje no ejecuta una correccion todavia.

## Ejecutar localmente (PowerShell)

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
$env:META_VERIFY_TOKEN = 'elige-un-valor-privado'
.venv/Scripts/python -m uvicorn bootstrap.main:app --port 8000 --no-access-log
```

Las variables de `.env.example` documentan la configuracion; el servidor no carga
archivos `.env` automaticamente. Configurar variables en la consola o en Render.
Nunca compartir tokens, archivos `.env` ni claves privadas en el repositorio.

## Validacion

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check bootstrap harness tests
.venv/Scripts/python -m ruff format --check bootstrap harness tests
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

El esquema se inicializa al arrancar, dentro de una transaccion y con un lock de
transaccion para evitar carreras entre instancias. Cada migracion tiene checksum;
una migracion aplicada no se edita. No hay borrados ni reversiones automaticas de datos.

`/health` comprueba que el servidor responde. `/ready` comprueba PostgreSQL y el
esquema: devuelve 200 con `database: ok` cuando estan disponibles, o 503 ante un fallo.
El campo `receiver_configured` indica si estan presentes los ajustes de recepcion;
`agents: pending` deja claro que los agentes aun no estan implementados.
Los errores de conexion se registran por clase, sin imprimir DSN ni contrasenas.

Las peticiones POST solo se confirman despues del commit en PostgreSQL. Las
transacciones de psycopg confirman al salir del contexto o revierten si hay un error:
https://www.psycopg.org/psycopg3/docs/basic/transactions.html

Un handshake exitoso solo prueba el GET de verificacion, no la recepcion completa.
El aviso actual del panel de Meta exige publicar la aplicacion para entregar datos
de produccion. Revisar esos requisitos antes de asumir que un mensaje del telefono
llegara al callback; las pruebas enviadas desde el panel son una evidencia distinta.

Render Free puede suspender el servicio por inactividad. No agregar metodo de pago
ni cambiar de plan para esta demo sin revisar primero sus condiciones y cuotas.

## Proximas etapas

1. Habilitar GitHub App para los agentes y evaluar correcciones con Groq.
2. Implementar y validar respuesta desde nuestro servidor por WhatsApp.
3. Construir CRUD, filtros y pruebas de la aplicacion de tareas.
4. Implementar arnes, revision y correcciones aisladas.
5. Proteger main, automatizar integracion y despliegue con comprobacion del SHA.
6. Ejecutar los dos recorridos reales y preparar evidencias y defensa.

Ver [conexion y comprobacion del almacenamiento](docs/almacenamiento.md).
Si falla una entrega, ver [diagnostico WhatsApp](docs/diagnostico-whatsapp.md).

Paginas publicas: `/privacy` y `/data-deletion`. Ver
[configuracion de privacidad y atencion de solicitudes](docs/privacidad.md).

El workflow **Gemini API check** verifica acceso al modelo con una peticion
sintetica desde main. Configuracion y limites en [verificacion Gemini](docs/gemini.md).
El primer intento remoto fallo por timeout de red, sin confirmar la clave ni la cuota.
**Groq API check** confirmo acceso y una generacion real con openai/gpt-oss-120b,
usando el secreto independiente GROQ_API_KEY. Esto no mide cuota restante ni calidad
de correccion de codigo. Ver [verificacion Groq](docs/groq.md).
Ninguno de los controles procesa mensajes reales de WhatsApp.

**GitHub App check** valida la app dedicada, el alcance de un unico repositorio y
la emision de tokens con permisos acotados. No modifica archivos ni crea PR en
esa prueba. Ver [GitHub App](docs/github-app.md).
