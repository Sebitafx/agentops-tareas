# Progreso verificable de los retos

Actualizado el 4 de noviembre de 2026, hora de Lima. Checklist manual: no ejecuta
trabajo en segundo plano. Implementacion, validacion local y demostracion en la
nube son evidencias diferentes.

## Comprobado en la nube

- [x] Receptor observado en 1ae84ea con base, respuestas y despachador activos.
- [ ] Confirmar envio con el nuevo token de sistema: /me y lectura del numero
      correctos segun capturas; POST de envio pendiente. El 400 actual no distingue
      causa con el codigo desplegado, por eso se agrega diagnostico numerico.

## Iteracion de comandos y diagnostico (rama de mantenimiento)

- [x] Listado de palabras clave en bienvenida, respuestas y callbacks.
- [x] Sin comando valido no se crea job ni se reanuda una aclaracion.
- [x] responder UUID detalle exige remitente propietario y estado needs_input.
- [x] Codigos y subcodigos Meta numericos en fallos genericos, sin cuerpo privado.
- [x] 59 pruebas especificas con PostgreSQL local aprobadas; lint y formato correctos.
- [x] Suite completa aislada: 337 pruebas aprobadas, cuatro escenarios separados
      omitidos, cobertura 82,34%; PostgreSQL y Chromium reales, lint/formato/tipos.
- [ ] Publicacion por PR, CI y despliegue de esta iteracion.

## Evidencia anterior (conservar alcance y fecha de cada prueba)

## Correccion de contexto para encabezados

### Fallo real posterior y reparacion del diagnostico

- Workflow 41790073827 para solicitud 14cac493: 341 pruebas pasaron y fallo solo
  una prueba nueva de IA, test_heading.py. Page.goto recibio una funcion porque
  el test omitio el parametro de fixture tasks_url. No se creo PR ni despliegue.
- El segundo intento intento una ruta protegida. El controlador sustituyo el
  diagnostico anterior por PROTECTED_PATH y el tercer intento perdio esa causa.
- Se conserva ahora el ultimo fallo de validacion tras propuestas prohibidas o
  JSON invalido, sin acumular parches ni ampliar los tres intentos. Dos regresiones
  reproducen ambas secuencias y conservan las pruebas de referencia intactas.
- El prompt explica la inyeccion de tasks_url como parametro y muestra un ejemplo
  completo. Para etiquetas no exige inventar una prueba adicional al E2E existente.
- Pendiente validar la nueva version con IA real. Las regresiones usan proveedor
  simulado; no acreditan por si solas un cambio ni despliegue reales.

- [x] Detectado: la solicitud de encabezado sin palabra texto/boton elegia Python,
      dejando al modelo sin HTML/JS ni sus hashes. El workflow 41788460438 fallo
      sin artefacto de validacion; no conserva el motivo interno de cada intento.
- [x] Seleccion por texto visible citado y terminos encabezado/cabecera/heading;
      HTML y JS juntos para conservar el texto despues de resetForm.
- [x] Se mantienen prioridad de rutas explicitas, estilos y exclusion de tests privados.
- [x] Motivos estables por intento en logs y respuesta fallida, con enlace a Actions;
      sin publicar prompts, propuestas ni diagnosticos crudos.
- [x] E2E exige conservar el encabezado inicial tras crear/editar sin fijar su texto.
      Suite aislada de esta correccion: 341 pruebas aprobadas, cobertura >=80%.
- [ ] Integrar la correccion y repetir la solicitud real del participante.

- [x] CRUD publico con PostgreSQL, filtros y API en agentops-tasks.
- [x] Recepcion real de WhatsApp, firma, lista de remitentes y persistencia en Neon.
- [x] Respuesta real de saludo/ayuda, registro de solicitudes y consulta de estado.
- [x] Propuesta real de Groq validada en Docker, sin PR ni despliegue.
- [x] CI aprobada del puente WhatsApp → Actions, commit daee926.

[CI daee926](https://github.com/Sebitafx/agentops-tareas/actions/runs/41758314695).
[Evaluacion real anterior](https://github.com/Sebitafx/agentops-tareas/actions/runs/41747916063).
El receptor mostrado por el participante sigue en la version de respuestas;
no hay evidencia aun de que ejecute el puente actualizado.

## Implementado y publicado en b7b74ff

- [x] Despacho duradero a Actions, API privada, claim exclusivo y callbacks con lease.
- [x] Aclaracion: retomar el mismo UUID solo con respuesta del mismo remitente.
- [x] Ayuda natural: comandos y preguntas de capacidades no crean cambios.
- [x] Propuestas acotadas, Ruff, maximo tres intentos y Docker sin red ni secretos.
- [x] Publicacion de rama y PR con hashes y base comprobados.
- [x] Integracion: proteccion estricta, CI aprobada y comprobacion de SHA/arbol.
- [x] Despliegue por commit, comprobacion de salud/version y restauracion ante fallo.
- [x] Revisor de pushes autorizado, hallazgos, reparacion, PR y prevencion de bucles.
- [x] Pruebas de proveedores, fallos de CI/despliegue y concurrencia.
- [x] Recorrido local webhook → PostgreSQL → Docker real → callbacks probado;
      GitHub, IA y Render simulados en ese test.
- [x] Benchmarks independientes de limite de titulo, texto del boton, buscador y aclaracion preparados.
- [x] Guias de activacion, variables por servicio y matriz de validacion preparadas.
- [x] Suite completa repetida tras corregir el fallo del comprobador de evaluacion:
      313 pruebas aprobadas, cuatro casos separados omitidos y 81,78% de cobertura.
      PostgreSQL, lint, formato, mypy y Chromium aprobados.
- [x] Publicar b7b74ff y comprobar Bootstrap CI aprobada:
      https://github.com/Sebitafx/agentops-tareas/actions/runs/41763615116.
- [x] Broker local repetido: webhook, PostgreSQL, Docker real y callbacks aprobados.
- [x] Controles independientes: la version original falla y una correccion conocida
      aprueba tanto el limite de titulo como el texto del boton.
- [ ] Aprobar la evaluacion ampliada de IA. Primer resultado b7b74ff: limite
      aprobado, boton/buscador agotaron intentos y peticion ambigua genero cambio.
      No se creo PR ni se desplegaron esos candidatos. Diagnosticos revisados.

## Correcciones posteriores en validacion

- [x] Conservar la causa del fallo en feedback, evitando que la tabla de cobertura
      la desplace. La cobertura se conserva como campo del reporte.
- [x] Instrucciones de pruebas UI ajustadas a Playwright instalado, sin fixtures de
      pytest-playwright que el proyecto no tiene.
- [x] Preguntas obligatorias antes de IA para peticiones vagas conocidas.
- [x] Oraculos UI distinguen textbox de su contenedor y toleran flecha decorativa
      sin perder la comprobacion de etiqueta y comportamiento tras guardar.
- [x] Suite corregida: 321 pruebas aprobadas, cuatro casos separados omitidos,
      cobertura 82,14%, PostgreSQL y Chromium reales, lint/formato/tipos correctos.
- [ ] Publicar estas correcciones por PR y repetir CI y evaluacion de IA.

## Presupuesto de contexto del proposer

- [x] Diagnostico acotado cuando codigo mas feedback superan 16000 caracteres:
      requisito y codigo completos, solo el feedback se recorta conservando
      causa y resumen con la marca ya usada por el validador aislado. Es lo que
      detuvo la reparacion del buscador. Pruebas del proposer 16 aprobadas,
      controles ruff/formato/mypy de taskapp aprobados y suite local en verde;
      pendiente repetir la evaluacion real de IA.

## Configuracion de cuentas

### Seleccion de proveedor para temas completos

- PR 12 integrado en 11bded2. Nueva solicitud completa enviada desde el WhatsApp
  del participante; ejecucion 41968209332 fallo INVALID_REQUEST en Groq antes
  de validar. No hubo evento de respaldo, PR ni despliegue. El registro antiguo
  no conserva el subcodigo del HTTP 400, por lo que su causa exacta no esta probada.
- Los temas que requieren HTML/JS/CSS ahora seleccionan Gemini directamente
  cuando su clave esta configurada. El resto conserva Groq y el respaldo acotado.
  Se registra proveedor y motivo; se mantienen contrato, alcance y validacion.
- Se mejora diagnostico de HTTP 400 reconociendo exclusivamente json_validate_failed,
  sin exponer mensajes externos, generacion fallida ni secretos. No se reintenta
  un HTTP 400 generico. Pendientes CI, merge y nueva prueba WhatsApp.
- Tarea ficticia de persistencia creada en la web antes del despliegue y guardada
  en artifacts/theme-cloud-persistence-probe.json. Pendiente comprobarla tras
  despliegue y eliminar exclusivamente ese registro de prueba.

### Corte de salida en la solicitud de tema

- PR 11 integrado en cef0eb2. Solicitud real 193f9515... reanudada por el
  participante en 41941059947 termino INCOMPLETE_PROPOSAL, antes de validar.
  El registro anterior no distinguia length de otros motivos de terminacion.
- Se identifica por separado el corte confirmado de salida en Groq/Gemini como
  PROPOSAL_OUTPUT_LIMIT. Groq puede pasar a Gemini por ese motivo, descartando
  el texto parcial. Otros rechazos incompletos no activan respaldo.
- Se agrega escenario sintetico task-theme con oraculo de navegador independiente,
  para comprobar la funcion real antes de otro merge. No crea PR ni despliega.
  Gemini real aprobado en 41945306398: fallo validacion en intentos 1 y 2,
  aprobo en intento 3. Candidato con HTML/CSS/JS y test nuevo; 392 pruebas
  aprobadas, 4 omitidas, 82,74 % de cobertura. Se comprobo que la aplicacion
  original sin tema falla el oraculo. Suite base: 390 aprobadas, 5 omitidas.
  Pendiente merge y nueva solicitud real WhatsApp: la anterior quedo failed
  y no se reanuda con responder. No se desplego el candidato sintetico.

### Aclaracion real y contexto de temas visuales

- PR 10 integrado en 806e5db. Se envio desde WhatsApp «Agregar un boton»:
  solicitud 193f9515-1c8b-4678-9860-4a4182ea0ac1, ejecucion 41938944115.
  Resultado NEEDS_INPUT con cero intentos IA y pregunta observada en WhatsApp.
- Se respondio por WhatsApp con modo oscuro/claro persistente, ubicacion en
  cabecera y prueba de navegador. Mismo UUID reanudado en 41939365322.
  Primer intento fallo porque el test nuevo omitio importar tasks_url; segundo
  produjo propuesta invalida y tercero pidio detalles tecnicos de CSS.
- Se completa el ejemplo de fixture, se instruye elegir clases CSS y se comparte
  HTML/JS/CSS para temas visuales. Contexto maximo 19000 caracteres y salida de
  propuestas Gemini hasta 8192 tokens; mismos controles de alcance y pruebas.
  Pendiente merge de esta correccion y repeticion real de la funcion solicitada.
- El analisis global de main conserva 20 hallazgos BUG/VULNERABILITY anteriores
  al PR, aunque el analisis del PR 10 aprobo sin hallazgos nuevos. Pendiente
  corregir los aplicables y revisar los relacionados con el aislamiento de demo;
  no se ha cambiado el quality gate ni se han suprimido reglas.

### Respaldo Gemini comprobado el 4 de noviembre

- Gemini 3.8 Flash devolvio timeout y luego HTTP 503 en las pruebas de acceso.
  Gemini 3.5 Flash-Lite supero acceso y genero el cambio sintetico de etiqueta
  al primer intento, validado en Docker sin red/secretos con oraculo E2E:
  [41937215387](https://github.com/Sebitafx/agentops-tareas/actions/runs/41937215387).
  Esa evaluacion no creo PR ni desplego la propuesta sintetica.
- El respaldo entra solo ante cuota de Groq, conserva diagnosticos e intentos
  restantes y exige las mismas politicas y pruebas. Se registra el proveedor.
  Si ambos fallan, se detiene; no se ha activado facturacion.
- Suite completa local del adaptador: 383 aprobadas, 4 omitidas, 82,66 %.
  Las omisiones corresponden a escenarios de benchmark y broker con Docker host,
  que se ejecutan por separado. Gemini real aprobo el benchmark de etiqueta.
- Se envio `hola` desde el WhatsApp del participante mediante control de la app
  y se observo respuesta del agente con los comandos. Pendiente probar la nueva
  aclaracion y su reanudacion despues de integrar el PR 10.
- PR 10: CI de push y PR aprobadas para ee0a6e3; SonarCloud detecto instalacion
  de dependencias sin hashes en el workflow nuevo. Se agrega requirements-dev.lock
  con versiones resueltas y hashes de wheels, instalacion solo binaria y limpieza
  de hallazgos de mantenibilidad. Pendiente nueva comprobacion de Sonar y merge.
- El conector GitHub devuelve 403 al integrar; control de Brave detenido por no
  poder verificar URL. No se cambia proteccion ni se extraen credenciales.

### Actualizacion del 4 de noviembre: aclaraciones y cuota

- Recorrido real confirmado por el participante: solicitud dd85cc4c-9d9d-4b7e-a4fe-2ccbddaae976,
  [ejecucion 41792177303](https://github.com/Sebitafx/agentops-tareas/actions/runs/41792177303),
  [PR 9](https://github.com/Sebitafx/agentops-tareas/pull/9), merge automatico ab9fdcc
  y encabezado publicado «Mis tareas». Las casillas historicas inferiores no
  sustituyen esta evidencia mas reciente.
- La solicitud «Agregar un boton» (768d4a77...) no entraba en el filtro previo
  de ambiguedad. Corregido: ahora pregunta accion, ubicacion y texto antes de
  consumir IA o validar cambios; falta comprobar la conversacion real tras el merge.
- La solicitud de modo oscuro (468f749b...) recibio QUOTA_OR_RATE_LIMIT en
  [41794098893](https://github.com/Sebitafx/agentops-tareas/actions/runs/41794098893).
  Ese registro no distingue cuota diaria de limite por minuto. El transporte
  ahora respeta Retry-After breve de Groq con hasta dos reintentos y un maximo
  de 120 segundos de espera. Sin cabecera util o con cuota persistente se detiene.
- Evaluaciones sinteticas con IA solo manuales; Bootstrap CI obligatorio sigue
  ejecutandose en push/PR. No se ha cambiado modelo ni activado facturacion.
- Estas correcciones afectan al controlador de Actions; no requieren despliegue
  manual del receptor en Render. Pendientes CI del PR, merge y prueba WhatsApp real.
- Validacion local completa en Docker sin red ni secretos: 364 pruebas aprobadas,
  4 omitidas, cobertura 82,51 %, lint, formato y tipos aprobados. Regresiones de
  aclaracion y transporte usan respuestas simuladas; no acreditan cuota real
  disponible ni la implementacion de modo oscuro.

- [x] GitHub App instalada solo en este repositorio; secretos de Actions configurados.
- [x] Variables de App en el receptor y hook de tareas en Actions configurados por el participante.
- [x] Administration Read-only agregado segun confirmacion del participante;
      pendiente de comprobar su emision de token desde Actions.
- [x] Participante creo regla clasica para main; comprobar configuracion estricta
      desde la App antes de integrar automaticamente.
- [ ] Desplegar manualmente la version final en Render y confirmar /version y /ready.
- [ ] Resolver token temporal de WhatsApp o documentar su renovacion para la demo.

## Demostracion final pendiente

- [ ] Solicitud real WhatsApp → workflow → PR → merge → version publicada → respuesta.
- [ ] Aclaracion real por WhatsApp y reanudacion de la misma solicitud.
- [ ] Funcion nueva real solicitada y comprobada en navegador.
- [ ] Push con incumplimientos y PR correctivo real; otro push valido.
- [ ] Persistencia comprobada despues de redesplegar.
- [x] Guion y preguntas de defensa academica preparados en demo.md y defensa.md.
- [ ] Registrar evidencia de ambos recorridos completos.

La revalidacion automatica de una base que cambia no esta implementada: se detiene
con REVALIDATION_REQUIRED y exige repetir desde main actual. No se anuncia exito
si la version y salud no quedan confirmadas. Ver [activacion](activacion-final.md),
[matriz](validacion-final.md) y [revisor](revisor.md).

## Donde mirar

- [Actions](https://github.com/Sebitafx/agentops-tareas/actions): queued/in progress/completed.
- [PR](https://github.com/Sebitafx/agentops-tareas/pulls): cambios y controles.
- [Historial](https://github.com/Sebitafx/agentops-tareas/commits/main/).
- [Aplicacion](https://agentops-tasks.onrender.com/).
- [Evidencias](evidencias.md).

Este archivo no sustituye una ejecucion activa ni acredita casos pendientes.

## Conversación de desarrollo por WhatsApp

La nueva ruta se activa al arrancar el receptor con OPENAI_API_KEY. Render interpreta el turno en segundo plano y Neon guarda el historial por remitente. En Actions, Sol medium lee o busca archivos de la aplicación y propone reemplazos por coincidencia única. El controlador publica los avances y comprueba el commit desplegado. Gemini y Groq son respaldos cuando su clave está disponible en el servicio que realiza la llamada.

**Activación:** integrar el PR con sus controles aprobados y desplegar ese commit en agentops-receiver. Abrir /ready y comprobar conversation_worker_running=true. Configurar GEMINI_API_KEY y GROQ_API_KEY también en el receptor para disponer de respaldo en la conversación. Las claves de Actions cubren el trabajo de código. El cambio solicitado en la demo se despliega en agentops-tasks por el pipeline.

El arnés reserva de forma atómica el coste máximo estimado antes de cada llamada a OpenAI. El límite de desarrollo es US$5 acumulados. AGENTOPS_DEMO=1 en el receptor habilita el saldo hasta US$10 **totales**. Las reservas se conservan aunque el proveedor falle o facture menos. Son un tope conservador, no una medición de la factura ni un control del uso externo de esa clave.

**Ensayo:** escribir «Pon un botón», contestar «Para cambiar entre modo oscuro y claro y recordar mi elección», y preguntar «¿Cómo va?». Comprobar un solo trabajo, avisos por fase, PR, pruebas, coincidencia con /version y persistencia del tema después de recargar. Medir desde el primer mensaje hasta la primera respuesta y desde la solicitud completa hasta la versión verificada. La ejecución con credenciales reales y los tiempos de producción requieren el despliegue del receptor.
