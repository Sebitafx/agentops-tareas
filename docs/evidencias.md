# Evidencias de integracion

## 30 de octubre de 2026 — servicio inicial

- Repositorio: https://github.com/Sebitafx/agentops-tareas
- Commit desplegado: `75611e003b03ec75dfd82ad8aeffae7c078c83d7`.
- GitHub Actions: primera ejecucion de Bootstrap CI finalizada con `success`.
- `GET https://agentops-receiver.onrender.com/health`: respuesta real
  `{"status":"ok","stage":"bootstrap"}`.
- `GET https://agentops-receiver.onrender.com/version`: commit coincide con el anterior.
- Meta: el participante confirmo recepcion de la plantilla de prueba y mostro un
  evento entrante de texto `Hola AgentOps` en el panel de Meta.

Esto acredita envio/recepcion dentro de Meta y disponibilidad del servidor por
separado. Todavia no acredita entrega de mensajes al servidor, almacenamiento,
ejecucion de agentes ni despliegue autonomo. No guardar numeros personales,
tokens ni cargas originales de mensajes en este repositorio publico.

## 3 de noviembre de 2026 — configuracion y almacenamiento

- El participante mostro el callback guardado y el indicador verde de configuracion
  de webhooks en Meta. No volver a solicitar la verificacion del GET sin un fallo nuevo.
- Neon: proyecto creado en Oregon; PostgreSQL activado y Better Auth desactivado.
- El participante confirmo `DATABASE_URL` guardada en Render; su valor no se compartio.
- Implementada bandeja PostgreSQL, migracion versionada, firma y autorizacion.
- Pruebas locales: 39 aprobadas, incluyendo PostgreSQL 16 real en Docker, migraciones
  concurrentes, rollback de lote, deduplicacion concurrente y persistencia tras reinicio.
- Cobertura de ramas y lineas combinada: 87.93%.
- La conexion real del nuevo codigo con Neon y la entrega de mensajes al callback
  todavia requieren desplegar y comprobar esta version.

## 3 de noviembre de 2026 — prueba real y diagnostico

- Render desplego el almacenamiento y luego las paginas de privacidad.
- `/ready` respondio `database: ok`, esquema `001_inbox.sql` y `receiver_configured: true`.
- Meta acepto el evento sintetico enviado desde su panel; el emisor y receptor
  ficticios no corresponden a los autorizados y no deben insertarse en Neon.
- El participante publico la app; Meta mostro confirmacion de modo activo.
- Las capturas confirman mensaje al numero de prueba correcto, texto correcto y
  campo messages suscrito, pero Neon devuelve cero filas en agentops_inbox.
- No se conoce aun si falta entrega de Meta o si el evento se descarta por filtros.
- Se agregan logs de recepcion, rechazo y descarte sin cuerpos ni identificadores
  personales. No se ha debilitado firma ni autorizacion para facilitar la prueba.
- 46 pruebas aprobadas contra PostgreSQL local; cobertura 87.80%. Imagen construida.
- Prueba de contenedor: eventos ficticios producen logs visibles diferenciando
  `messages=0 ignored_phone_changes=1` y `messages=1` tras confirmar transaccion.
- La revision de suscripcion WABA y la entrega real siguen pendientes; no declarar
  alcanzados los retos por estas pruebas de infraestructura.

## 3 de noviembre de 2026 — recepcion real confirmada

- GET de subscribed_apps mostro inicialmente solo la aplicacion de pruebas de Meta.
- El participante suscribio AgentOps Tareas mediante POST y obtuvo `success: true`.
- Un GET posterior confirmo AgentOps Tareas entre las aplicaciones suscritas a la WABA.
- Despues de la suscripcion, el participante envio un texto nuevo desde su WhatsApp.
- Neon devolvio `mensajes_recibidos = 1` al consultar ese texto de prueba.
- Render mostro `stage=received` seguido de `stage=accepted messages=1 statuses=0`,
  con todos los contadores de descarte en cero.
- Queda verificado el recorrido real WhatsApp -> Meta -> Render -> PostgreSQL.
- La suscripcion de la aplicacion a la WABA era la vinculacion que faltaba para
  esta prueba, ademas de tener verificado el callback y suscrito el campo messages.
- Sigue pendiente enviar respuestas, implementar el gestor de tareas, los agentes
  de correccion/revision, la integracion automatica y el despliegue autonomo.

## 3 de noviembre de 2026 — preflight de Gemini

- El participante creo una clave dedicada y mostro GEMINI_API_KEY guardado como
  repository secret de Actions; el valor no se compartio ni se guardo en el codigo.
- Se agrega Gemini API check: maximo dos llamadas y un prompt sintetico, sin mensajes
  de WhatsApp, DB ni codigo del repositorio enviado al proveedor.
- Validacion local con respuestas simuladas: 72 pruebas aprobadas, cobertura 89.98%.
- La primera ejecucion remota debe confirmar por separado acceso real y generacion;
  las pruebas locales no certifican validez de la clave ni cuota de la cuenta.

## 3 de noviembre de 2026 — resultado Gemini y alternativa Groq

- Bootstrap CI del preflight Gemini finalizo con success.
- Gemini API check fallo por NETWORK_ERROR tras 30 segundos, sin HTTP status.
  No se confirmo acceso, validez de clave, cuota ni saturacion del proveedor.
- El conector GitHub no tuvo permiso para reejecutar el job (403). La revision
  automatica bloqueo usar credenciales de Git para suplir ese permiso; esa accion
  no se ejecuto. Cualquier reintento debe usar la UI o un mecanismo autorizado.
- El participante eligio probar Groq y mostro GROQ_API_KEY guardado en Actions.
- Se agrega control acotado de catalogo y generacion, compartiendo el transporte
  con Gemini sin habilitar fallback ni procesamiento de mensajes personales.
- 93 pruebas locales aprobadas, con PostgreSQL real y proveedores simulados;
  cobertura combinada 91.04%. La validacion real de Groq se documentara por separado.

- Primer intento real de Groq: HTTP 403. Una prueba publica sin claves reprodujo
  el 403 y su marcador de rechazo del cliente predeterminado de urllib.
- Al identificar transparentemente el cliente como AgentOps-Tareas, la misma ruta
  publica respondio 401 (autenticacion requerida), sin el marcador anterior.
- Se agrega ese User-Agent al transporte. Las 47 pruebas de proveedores pasaron;
  falta confirmar la generacion real del cliente corregido con la clave de Actions.

## 3 de noviembre de 2026 — Groq validado

- Commit `3908c6893bf60b154f2e357c971cf3cb8e49d588`.
- [Groq API check](https://github.com/Sebitafx/agentops-tareas/actions/runs/41708394926)
  finalizo con success: provider groq, modelo openai/gpt-oss-120b, model_access true
  y generation_confirmed true. Se envio unicamente el prompt sintetico.
- [Bootstrap CI](https://github.com/Sebitafx/agentops-tareas/actions/runs/41708394935)
  del mismo commit finalizo con success.
- La identificacion transparente del cliente resolvio el rechazo observado de Groq.
- El resultado no certifica cuota restante, modalidad de facturacion ni calidad de
  correccion de codigo. Los mensajes de WhatsApp siguen sin enviarse a la IA.
- Queda pendiente GitHub App, aplicacion CRUD, arnes de correccion/revision,
  respuestas WhatsApp y despliegue autonomo.

## 3 de noviembre de 2026 — GitHub App preparada

- El participante registro agentops-tareas-sebitafx e instalo la App en su cuenta.
- La pantalla de instalacion confirma Metadata read y Actions, Contents y Pull
  requests read/write. La seleccion de repositorios se comprueba en la prueba remota.
- AGENT_APP_ID y AGENT_APP_PRIVATE_KEY aparecen guardados en Actions; no se
  recibieron sus valores ni se guardo el PEM en este repositorio.
- GitHub App check usa la accion oficial para emitir y revocar tokens efimeros.
  Comprueba alcance con Metadata read antes de pedir permisos del repo especifico.
- 22 pruebas locales del comprobador aprobadas. La autenticacion real y el alcance
  deben acreditarse con la ejecucion de Actions, no con estas pruebas simuladas.

## 3 de noviembre de 2026 — GitHub App validada

- [GitHub App check](https://github.com/Sebitafx/agentops-tareas/actions/runs/41711500643)
  termino con success en el commit 6cf5dac51cfbb45d8d2439f2d6a453b844c0ef93.
- El token Metadata mostro un unico repositorio accesible: Sebitafx/agentops-tareas.
- GitHub emitio el token limitado con Contents, Pull requests y Actions write.
- Consultas de repo, main, PR y workflows correctas. No se probo una escritura.
- Los dos pasos post de revocacion de tokens terminaron correctamente.
- Bootstrap CI del mismo commit termino con success.

## 3 de noviembre de 2026 — aplicacion de tareas

- CRUD, filtros y UI responsive implementados con migracion aditiva 002_tasks.sql.
- 133 pruebas locales de API/integracion aprobadas con PostgreSQL real, cobertura
  combinada 92.41%, lint/formato correctos y mypy sin errores en taskapp.
- Un E2E adicional en Chromium completo CRUD, filtros, persistencia al recargar,
  eliminacion, viewport movil y verificacion de que HTML no se ejecuta.
- Capturas locales en artifacts/tasks-desktop.png y tasks-mobile.png; revisadas.
- Imagen Docker construida. Ambos roles arrancaron contra PostgreSQL local real:
  /health y /ready respondieron 200; tasks tambien sirvio /api/tasks con datos.
  El receptor sin secretos de Meta reporto receiver_configured false, como corresponde.
- El gestor en Render y su persistencia en Neon siguen pendientes de desplegar.
