# Puente de solicitudes reales a PR

Implementado y probado localmente; el recorrido en la nube debe confirmarse aparte.
whatsapp-agent.yml solo acepta UUID de una solicitud guardada y corre desde main del
repositorio autorizado. El texto del participante no se pasa como input publico del
workflow ni como comando. No se crea un agente nuevo para los commits del bot.

## Receptor

004_jobs.sql conserva los registros anteriores y agrega metadatos de despacho y
ejecucion. Las respuestas usan event_key unico, permitiendo confirmacion inicial y
notificaciones posteriores sin duplicar cada evento. No modifica migraciones previas.

El despachador reclama el trabajo mas antiguo, deja la transaccion y llama GitHub
con un token efimero, limitado a actions write. Un maximo de tres despachos y una
espera entre ellos permiten recuperar solicitudes cuyo workflow no haya reclamado
el trabajo. El receptor no despacha otra solicitud mientras una este ejecutandose.
El workflow tambien serializa ejecuciones con un grupo de concurrencia compartido.

El endpoint privado claim requiere el secreto de control derivado del PEM compartido
en Render y Actions. Cambia received a running bajo lock y entrega un lease aleatorio.
Un segundo workflow recibe 409 y termina sin trabajo. progress requiere el mismo
lease, valida estados y guarda estado y respuesta en una transaccion. Un lease de
otra ejecucion se rechaza. Callbacks repetidos no duplican notificaciones.

Si el agente pregunta, el estado pasa a needs_input. El comando responder UUID detalle
del mismo numero retoma esa pregunta, conserva el id e invalida el lease anterior.
No se reanuda con texto libre ni se interpreta una peticion nueva como respuesta.
Solo los comandos de cambio admitidos crean trabajos; los mensajes no reconocidos
reciben reglas. Ver [comandos](comandos-whatsapp.md). El texto acumulado sigue sujeto
al limite del arnes; no se recorta silenciosamente para intentar aprobarlo.

Un trabajo running sin actualizaciones durante 45 minutos, o un despacho sin
reclamacion tras tres intentos, queda failed y se consulta con estado UUID. Esta
version no ofrece reanudacion automatica de una ejecucion interrumpida a mitad de PR.

## Workflow confiable

El controlador autentica su consulta al receptor, selecciona un contexto acotado del
codigo publico, llama Groq y ejecuta el arnes con Ruff y DockerValidator. Un fallo
no crea PR. Una pregunta vuelve por WhatsApp. Un resultado validated se entrega al
publicador protegido y produce PR y enlace de ejecucion en la respuesta de WhatsApp.
El coordinador recibe los secretos; el contenedor del candidato no los recibe.

Seleccion de contexto actual: rutas explicitas si se mencionan, HTML/JS para textos
y botones, CSS/HTML para estilos, Python para logica del servidor. Es una seleccion
acotada, no una herramienta general de exploracion. Una solicitud amplia puede
requerir aclaracion, exceder contexto o detenerse; no se garantiza cualquier cambio.

Con RENDER_TASKS_DEPLOY_HOOK en Actions, comprueba proteccion estricta y espera CI
del head antes de integrar. Vuelve a comprobar base y head, usa merge con SHA y
verifica padres y arbol del resultado. Despliega ese commit y comprueba /version,
/health, /ready y lectura de tareas antes de succeeded. Si falla, intenta restaurar
el commit anterior y registra resultado; no revierte datos. Sin hook queda pr_open.
Una base que cambia detiene la operacion y requiere repetir desde la base actual.
El segundo reto usa la misma integracion: ver [revisor](revisor.md).

## Activacion y prueba

Esperar CI aprobada y desplegar el commit del puente en agentops-receiver. Las
variables de GitHub App deben coincidir con Actions; no agregar claves al repositorio.
La politica de privacidad actualizada informa el uso de Groq y GitHub para solicitudes.
Solo usar datos ficticios. El token temporal de WhatsApp puede necesitar renovacion.

Escribir una peticion concreta, por ejemplo cambiar un texto del boton. Deben verse:
registro con id, workflow WhatsApp agent, validacion del candidato, PR y respuesta con
links. Verificar estos hechos y el contenido del PR antes de marcar el recorrido
como demostrado. El estado de ayuda nunca debe afirmar un despliegue que no ocurrio.
