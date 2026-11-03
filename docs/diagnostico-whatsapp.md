# Diagnosticar un mensaje real que no aparece en Neon

Confirmado en la demo: numero y texto correctos, app publicada, campo messages
suscrito, evento sintetico de Meta aceptado. Neon sigue con cero mensajes.
Esto no basta para atribuir el fallo a Meta o a los filtros del receptor.

## 1. Distinguir llegada, rechazo y descarte

Desplegar la version con diagnostico, abrir `/health`, esperar su respuesta y enviar
un mensaje nuevo desde el numero autorizado. En Render > Logs buscar `whatsapp_delivery`:

| Resultado | Interpretacion y siguiente comprobacion |
|---|---|
| No aparece `stage=received` | No hay evidencia de llegada al handler. Probar el boton Test de Meta y revisar entrega/suscripcion de cuenta. |
| `reason=configuration` | Faltan variables o su formato no es valido. |
| `reason=signature` | Firma ausente o no coincide con META_APP_SECRET; revisar que sea de esta app. |
| `reason=payload` | El JSON firmado no coincide con la estructura esperada. Inspeccionar privadamente la estructura en Meta, ocultando datos personales. |
| `reason=storage_not_ready` o `reason=database` | No se confirmo la entrega: comprobar /ready y PostgreSQL. |
| `stage=accepted messages=0 ignored_phone_changes=1` | El Phone Number ID del evento no coincide con el configurado; comparar IDs en privado. |
| `stage=accepted messages=0 ignored_senders=1` | El remitente no coincide con la lista permitida; comparar en privado. |
| `stage=accepted messages=0 ignored_types=1` | El mensaje no es texto. |
| `stage=accepted messages=1` | La transaccion se confirmo; consultar Neon y comprobar base y rama seleccionadas. |

`messages` cuenta mensajes autorizados de una entrega, no nuevas filas: un reintento
puede mostrar messages=1 sin insertar otra fila por la deduplicacion.
El `id` de diagnostico es aleatorio por peticion y no es el ID de mensaje de Meta.
No se imprimen mensajes, telefonos, identificadores de Meta ni firmas.
Los eventos sinteticos suelen tener un Phone Number ID ficticio: su descarte es esperado.

## 2. Comprobar la suscripcion de la app a la cuenta WABA

Ademas de suscribir el campo messages, Meta documenta la suscripcion de la app a
la WhatsApp Business Account (WABA):

- [Listado de suscripciones, coleccion oficial de Meta](https://www.postman.com/meta/whatsapp-business-platform/request/tl2wk2j/get-all-subscriptions-for-a-waba).
- [Suscribir una app, coleccion oficial de Meta](https://www.postman.com/meta/whatsapp-business-platform/request/26gui66/subscribe-to-a-waba).

En [Graph API Explorer](https://developers.facebook.com/tools/explorer/), seleccionar
AgentOps Tareas y un token de esa app con acceso a su WABA y permiso de gestion de
WhatsApp. Generar o autorizar el token solo en Meta; nunca pegarlo en chat, URL publica,
captura ni repositorio. Elegir la version de la API que muestra el panel.

Primero hacer una consulta **GET** a:

```text
IDENTIFICADOR_DE_LA_CUENTA_DE_MENSAJES/subscribed_apps
```

Usar el ID de la cuenta de mensajes de Paso 1, no el Phone Number ID ni el telefono.
Comprobar si aparece el App ID de AgentOps Tareas (Configuracion > Informacion basica).
Si la respuesta es vacia, valorar suscribir la app mediante **POST** al mismo recurso,
con el token correcto. Volver a hacer GET y verificar. No eliminar otras suscripciones.
Si hay un error de permisos o token, resolverlo antes de interpretar el resultado
como ausencia de suscripcion. Un POST exitoso acredita la suscripcion, no la entrega
real ni la persistencia: repetir despues la prueba WhatsApp -> receptor -> Neon.

## 3. Numero de prueba y produccion

La documentacion de recepcion de Meta describe enviar mensajes al numero de prueba:
https://whatsapp.github.io/WhatsApp-Nodejs-SDK/receivingMessages/

Los pasos del asistente para registrar numero propio, agregar metodo de pago y
verificar empresa no diagnostican por si solos la entrega del numero de prueba.
No completarlos ni cambiar de modalidad para ocultar el fallo. Si Meta requiere
alguno explicitamente para este activo, documentar el requisito y revisar el alcance
y costo antes de continuar. La demo real sigue pendiente hasta comprobar una fila en Neon.
