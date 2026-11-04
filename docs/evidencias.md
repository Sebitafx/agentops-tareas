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

## 3 de noviembre de 2026 — gestor publicado

- [Aplicacion](https://agentops-tasks.onrender.com/) desplegada por el participante.
- /version confirmo 901422f1e8c5fdea5b43598faeba07cd8399c580. El receptor tambien
  confirmo ese commit. /health y /ready del gestor devolvieron ok, database ok,
  schema_version 002_tasks.sql.
- [CI del commit](https://github.com/Sebitafx/agentops-tareas/actions/runs/41713979261):
  134 pruebas aprobadas, cobertura 92.41%, Ruff, mypy, Chromium y Docker correctos.
- Comprobacion HTTP real: crear tarea ficticia, editarla, completarla, filtrar en
  pendientes/completadas, leerla en una nueva peticion, eliminarla y confirmar 404.
  Solo se elimino la tarea creada por esta comprobacion.
- Evidencia local resumida artifacts/cloud-tasks-check.json, sin credenciales.
- La persistencia tras redesplegar aun requiere demostracion independiente.

## 3 de noviembre de 2026 — contrato y motor del arnes

- Propuestas estructuradas, alcance por rutas/hashes y bucle de tres intentos.
- Adaptador Groq y comprobacion sintetica implementados; resultado remoto pendiente.
- Las pruebas del motor simulan el validador. Aun no se ejecuta codigo generado,
  no se crean PR ni se conectan mensajes reales con el motor.

- [Agent proposal check](https://github.com/Sebitafx/agentops-tareas/actions/runs/41717273957)
  termino con success para 1c083c7a2422a85f9ad256bb7256116b2e51ece9. Propuesta sintetica
  guardada como artefacto, sin aplicar ni ejecutar. CI del mismo commit aprobada.

## 3 de noviembre de 2026 — envio de respuestas preparado

- Migracion 003 agrega solicitudes y cola de salida; insercion atomica y deduplicada.
- Ayuda, registro de peticiones y estado por remitente, sin procesamiento real con IA.
- Proceso de fondo con reclamaciones concurrentes, comprobacion de destinatario,
  errores sanitizados, vencimiento de respuestas y reintentos de tasa limitados.
- Resultado ambiguo de red o interrupcion queda uncertain: no se promete exactly once.
- 225 pruebas locales aprobadas, cobertura combinada 92.64%, Ruff y mypy correctos;
  Chromium completo el E2E y la imagen Docker se construyo.
- El participante mostro WHATSAPP_TOKEN configurado y oculto en Render.
- Despliegue y mensaje real de ida/vuelta pendientes; no se acredita envio con mocks.

## 3 de noviembre de 2026 — respuesta real de WhatsApp confirmada

- Render publico 157fd0151c49ddf728751bd1be0003f59bfba605. /ready confirmo
  003_replies.sql, receiver_configured true, reply_sender_configured true y
  reply_worker_running true.
- [CI del envio](https://github.com/Sebitafx/agentops-tareas/actions/runs/41733190778):
  225 pruebas y 92.89% de cobertura en Linux.
- El participante envio hola y mostro la respuesta de ayuda recibida a las 17:49
  (Lima). Evidencia real de ida/vuelta, distinta de una simulacion de proveedor.
- La respuesta informa que el agente de correccion aun no esta conectado. No se
  acredita correccion, PR, integracion ni despliegue autonomo con ese saludo.
- El participante configuro en privado AGENT_APP_ID y AGENT_APP_PRIVATE_KEY en
  Render, y RENDER_TASKS_DEPLOY_HOOK en Actions. No se recibieron sus valores.

## 3 de noviembre de 2026 — validacion aislada local

- DockerValidator y offline_runner ejecutaron 245 pruebas con cobertura 87.22%.
- Las comprobaciones internas confirmaron UID sin privilegios, raiz readonly e
  interfaz de red exclusivamente loopback. PostgreSQL fue local al contenedor y
  Chromium completo E2E. No se entregaron secretos ni acceso a Neon.
- Pruebas adicionales verifican rechazo de borrados, reemplazos de tests, symlinks,
  reportes incompletos y falta de aislamiento, ademas de limpieza tras timeout.
- Primera ejecucion detecto clasificacion de imports distinta por rutas de proyecto;
  se declaran los paquetes propios de Ruff. Segunda detecto rutas de mypy, alineadas
  con PYTHONPATH. Se conservaron las reglas y las pruebas de comportamiento.
- La nueva evaluacion de propuesta real en Actions esta pendiente de su ejecucion.

## 3 de noviembre de 2026 — propuesta real validada

- [Evaluacion real](https://github.com/Sebitafx/agentops-tareas/actions/runs/41747916063)
  aprobo en el primer intento para 2bf86a3a96b4755e6029e0e69fe9e5d9c5564e67.
  status validated, isolated_validation_passed true; sin cambiar checkout, crear PR
  ni desplegar. CI del mismo commit tambien aprobo.
- El intento anterior agoto tres validaciones por imports en una nueva prueba.
  Ruff normaliza imports y formato sobre stdin sin ejecutar el codigo propuesto;
  se mantuvieron las pruebas y las reglas de validacion.
- Cliente Python de GitHub App preparado y probado con RSA ficticio; pendiente
  su uso real desde el receptor. No se consultaron claves privadas del usuario.

## Publicador de PR preparado

- Control de candidato aprobado, hashes, base vigente y rama nueva por UUID.
- 264 pruebas en contenedor sin red aprobadas, cobertura 86.46%.
- Los tests de publicacion simulan GitHub; no se ha creado un PR real con ese modulo.
- Pendientes: despachar solicitudes, callbacks, PR real, proteccion de main,
  integracion con revalidacion y despliegue comprobado.
