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
