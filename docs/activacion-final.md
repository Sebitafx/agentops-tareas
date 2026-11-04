# Activacion final

## 1. GitHub App

En [permisos de la App](https://github.com/settings/apps/agentops-tareas-sebitafx/permissions):
Contents, Pull requests y Actions: Read and write. Administration: Read-only.
Metadata: Read-only. Guardar y aceptar el cambio de permisos de la instalacion.
Mantener Only select repositories → agentops-tareas. Sin permisos de workflows
ni administracion de escritura. El workflow GitHub App check debe aprobar.

Actions → Repository secrets: AGENT_APP_ID, AGENT_APP_PRIVATE_KEY, GROQ_API_KEY,
RENDER_TASKS_DEPLOY_HOOK. Este ultimo es el hook privado de agentops-tasks, no del
receptor. No publicar valores. GEMINI_API_KEY es opcional, para su comprobador.

## 2. Proteger main despues de publicar esta version

En [Settings → Branches](https://github.com/Sebitafx/agentops-tareas/settings/branches),
Add classic branch protection rule, patron main:

1. Require a pull request before merging. Para esta demo individual, desmarcar
   Require approvals; se exige PR y controles, sin aprobacion humana obligatoria.
2. Require status checks to pass before merging → bootstrap-quality.
3. Require branches to be up to date before merging.
4. Do not allow bypassing the above settings (aplicar tambien a administradores).
5. No permitir force pushes ni borrados. No dar bypass al bot.
6. No activar Require linear history: este pipeline verifica un merge con dos padres.

La regla debe ser clasica: se consulta /branches/main/protection. No se salta una
proteccion incompatible; se detiene y reporta. Tras proteger main, los cambios
manuales tambien se hacen por rama y PR.

## 3. Render y despliegue manual inicial

Ambos servicios: Docker, Free, main, build context ., Dockerfile ./Dockerfile,
health check /health, Auto-Deploy Off. Sin Pre-Deploy Command. No cambiar a plan pago.

agentops-tasks: DATABASE_URL privado de Neon y SERVICE_ROLE=tasks. No entregar
los otros secretos a este servicio.

agentops-receiver: DATABASE_URL, SERVICE_ROLE=receiver, META_VERIFY_TOKEN,
META_APP_SECRET, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_ALLOWED_SENDERS, WHATSAPP_TOKEN,
AGENT_APP_ID, AGENT_APP_PRIVATE_KEY. Mismo PEM completo que en Actions; no el nombre
del archivo ni Client Secret. No necesita Groq ni el hook de Render.

Esperar Bootstrap CI aprobada para el commit final. En cada servicio, Manual Deploy
→ Deploy a specific commit y pegar ese SHA; si se usa Deploy latest commit, comprobar
que Source coincide. Actualizar ambos servicios una vez. Las siguientes solicitudes
publican tareas mediante el hook; no redespliegan el receptor.

Comprobar /version en ambos. En receptor /ready: database ok, schema_version
004_jobs.sql, receiver_configured true, reply_sender_configured true,
reply_worker_running true, agent_configured true y agent_dispatcher_running true.
Las banderas indican configuracion y proceso vivo; los mensajes y workflows reales
comprueban si Meta y GitHub aceptan las credenciales.

## 4. WhatsApp y credencial

Conservar callback https://agentops-receiver.onrender.com/webhooks/whatsapp,
campo messages suscrito y App suscrita a la WABA. Se usa el numero de prueba de
Meta, no se registra el telefono personal como numero empresarial.

WHATSAPP_TOKEN es distinto de META_VERIFY_TOKEN. El temporal del panel ya fallo
como invalid/expired. Para una demo estable, usar un token de usuario del sistema
si Meta lo permite: Business settings → Users → System users, asignar App y activo
WhatsApp, generar token con whatsapp_business_messaging y acceso al activo requerido.
Elegir la duracion permitida y guardarlo directamente en Render. Si la cuenta no
ofrece esa opcion, renovar el temporal antes de la demo y registrar la limitacion.
No se auto-renueva ni se promete vigencia permanente.

## 5. Prueba del participante

Seguir [demo](demo.md). Primero ayuda; luego peticion clara. No enviar varias pruebas
de IA a la vez. Abrir /health antes de probar para despertar el servicio gratuito.
La primera solicitud puede tardar por arranque y compilacion.

Si no responde: logs de Render, whatsapp_delivery y whatsapp_reply. Si el token
falla, renovarlo en privado. Si hay PR pero no integracion, revisar GitHub App check,
proteccion, bootstrap-quality y el motivo del workflow. No quitar controles.

Fuentes: [proteccion](https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection),
[hooks por commit](https://render.com/docs/deploy-hooks).
