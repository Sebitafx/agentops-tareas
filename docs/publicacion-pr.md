# Publicacion de una propuesta validada

harness/publish.py prepara un PR a partir del Outcome del coordinador confiable.
Requiere status validated, propuesta y candidato; comprueba politica, hashes y que
el contenido candidato coincide exactamente con el propuesto. No recibe comandos
ni nombres de rama del modelo. Usa UUID de solicitud, SHA y run ID verificados.

Antes de construir el commit y antes de publicar la rama, comprueba que main siga
en la base validada. Crea blobs y un arbol sobre esa base, un commit con ese padre
y exclusivamente una referencia nueva agentops/requests/UUID. Nunca fuerza ni
actualiza una referencia existente, integra main o invoca Render.

El cuerpo del PR incluye id, base y enlace de validacion. No copia texto de WhatsApp
ni el resumen del modelo. El resultado devuelve numero de PR, URL, head SHA y base.
Un fallo de red puede dejar objetos o una rama creada sin PR; este componente no
repite automaticamente escrituras cuyo resultado es incierto.

Los chequeos de main previenen publicar una base que ya se sabe desactualizada,
pero no son un bloqueo atomico de GitHub. Antes de integrar se deben comprobar
nuevamente base, head y controles, junto con la proteccion estricta de main.

Las pruebas verifican que no se publique sin validacion, que una alteracion posterior
del candidato bloquee la escritura y que un cambio de main impida crear la rama.
El cliente API se simula en estas pruebas: aun no acreditan una escritura real ni
una solicitud originada en WhatsApp. Falta conectar el despachador y el workflow.
