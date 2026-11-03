# Respuestas de WhatsApp

El receptor ahora puede responder ayuda, confirmar que registro una peticion y
consultar el estado de una solicitud propia. El agente que corrige y despliega codigo
aun no esta conectado. Las respuestas explican esa limitacion; no anuncian cambios
ni despliegues que no ocurrieron.

## Configuracion

Solo agentops-receiver recibe WHATSAPP_TOKEN. Es un token de Meta con permiso
whatsapp_business_messaging para el numero configurado, distinto del secreto de
aplicacion y del identificador propio de verificacion del webhook. El participante
lo guarda directamente en Environment de Render, nunca en el chat o en Git.
Los tokens de prueba son temporales: si vencen, se necesita renovarlos en Meta y
guardar la variable en Render. No cambiar planes ni registrar un telefono de pago.

META_GRAPH_VERSION es configurable y su valor inicial es v26.0, la version vista
en el panel de la demo. WHATSAPP_PHONE_NUMBER_ID y WHATSAPP_ALLOWED_SENDERS conservan
su configuracion de recepcion. El servicio tasks no necesita el token.

Desplegar en Render solo despues de CI aprobada. /ready del receptor debe informar
schema_version 003_replies.sql, reply_sender_configured true y reply_worker_running
true. Estas banderas comprueban presencia/formato y proceso activo, no validez del
token ante Meta. La prueba real consiste en escribir hola al numero de prueba y
recibir la respuesta en el telefono autorizado.

## Recorrido y garantias

1. Firma y remitente validos: el receptor guarda inbox, solicitud si corresponde y
   respuesta pendiente en una sola transaccion, antes de devolver 200 a Meta.
2. Un mensaje repetido conserva una sola solicitud y una sola respuesta, gracias a
   la clave unica del mensaje entrante. Los eventos de estado no generan respuestas.
3. Un proceso de fondo reclama una respuesta con FOR UPDATE SKIP LOCKED. Confirma
   la reclamacion antes de llamar a Meta; ningun lock se mantiene durante la red.
4. El envio usa HTTPS a graph.facebook.com con Bearer header, sin redirecciones,
   timeout de 10 segundos y respuesta limitada. Revalida destinatario y Phone ID.
5. Una respuesta exitosa se registra como sent con su id de proveedor. Significa
   aceptacion de Meta; delivered/read proceden de los webhooks de estado firmados.
6. Token vencido, permisos o ventana cerrada: fallo definitivo. Un limite de tasa
   explicitamente rechazado reintenta hasta tres veces con espera creciente.
7. Timeout, fallo de red/servidor ambiguo o caida durante el envio: uncertain;
   no se reenvia automaticamente. Una llamada podria haber sido aceptada y esta
   version no ofrece entrega exactamente una vez. Requiere revision manual.
8. Se descartan pendientes con mas de 23 horas desde el mensaje original, para no
   iniciar conversaciones fuera de la ventana de respuesta con texto libre.

Los logs muestran id interno aleatorio, resultado y motivo estable. No muestran
telefonos, cuerpos, token ni mensajes crudos de error de Meta. La migracion es
aditiva y no responde retroactivamente a mensajes que ya estaban en inbox.

## Comandos

- hola, ayuda, inicio, help o /start: instrucciones.
- Cualquier otra peticion: se registra con UUID y estado received.
- estado UUID: muestra solo una solicitud del mismo remitente.
- estado con id invalido o ajeno: ayuda o respuesta sin revelar datos ajenos.

Ante WHATSAPP_TOKEN_INVALID_OR_EXPIRED, renovar token y escribir un mensaje nuevo.
Ante WHATSAPP_HTTP_ERROR_403, revisar acceso al numero y permiso de mensajeria.
WHATSAPP_NETWORK_ERROR deja un envio incierto, no un envio confirmado ni un reintento.

Referencias de Meta:
- [Mensajes en el espacio oficial de Postman](https://www.postman.com/meta/whatsapp-business-platform/folder/o48mro7/messages).
- [Texto en el SDK oficial](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/text/).
