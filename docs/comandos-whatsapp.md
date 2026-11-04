# Comandos explicitos de WhatsApp

El saludo y las respuestas incluyen esta lista. El comando debe ir al principio;
se admiten mayusculas, espacios y dos puntos despues del comando de cambio.

| Comando | Resultado |
| --- | --- |
| hola / ayuda | Mostrar funciones y reglas, sin crear trabajo |
| estado <id> | Consultar una solicitud del mismo remitente |
| cambiar <peticion> / cambia <peticion> | Crear una solicitud de cambio |
| corregir <problema> / corrige <problema> | Crear una solicitud de correccion |
| agregar <funcion> / agrega <funcion> | Crear una solicitud de funcion nueva |
| responder <id> <detalle> | Reanudar esa aclaracion pendiente del mismo remitente |

Ejemplo: cambiar el encabezado "Una cosa a la vez" por "Mis tareas".

Un texto desconocido, una palabra clave solo dentro de una frase o un comando de
cambio sin detalle devuelve las reglas. Se conserva la entrega para auditoria y
deduplicacion, pero no se crea un job ni se llama a IA o Actions.

Una aclaracion ya no se contesta con texto libre. Se exige responder, UUID y detalle,
para evitar que un saludo informal o una peticion nueva alteren un trabajo pendiente.
Los callbacks indican el comando que debe usarse para responder a la pregunta.
Los trabajos aceptados antes de esta version conservan su estado.

## Diagnostico del envio

El receptor puede aceptar un mensaje aunque Meta rechace nuestra respuesta. Para
errores genericos conserva solo HTTP, codigo numerico y subcodigo numerico, por
ejemplo WHATSAPP_HTTP_ERROR_400_META_100_SUB_33. Nunca guarda el mensaje crudo del
proveedor ni el token en logs. Se mantienen los limites de reintentos e incertidumbre.

El error de credencial 190/401 conserva WHATSAPP_TOKEN_INVALID_OR_EXPIRED; el token
se carga al arrancar. Cambiar WHATSAPP_TOKEN exige reiniciar o redesplegar el receptor.
Una respuesta a /me demuestra identidad, no acceso al numero de WhatsApp. Comprobar
asignacion de la aplicacion y la cuenta de WhatsApp al usuario del sistema.
