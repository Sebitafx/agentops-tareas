# Progreso verificable de los retos

Actualizado el 3 de noviembre de 2026, hora de Lima. Este archivo es una lista de
avance manual; no es un monitor en tiempo real ni ejecuta trabajo en segundo plano.

## Implementado y comprobado

- [x] Gestor CRUD publico con PostgreSQL, filtros y pruebas E2E.
- [x] Recepcion real de WhatsApp con firma, remitentes autorizados y deduplicacion.
- [x] Respuesta real de ayuda y registro duradero de solicitudes.
- [x] Contrato y politica de archivos para propuestas de IA, con tres intentos maximos.
- [x] Generacion real de propuesta sintetica con Groq y validacion Docker aislada.
- [x] Normalizacion de imports y formato mediante Ruff, sin ejecutar el texto propuesto.
- [x] Publicador de PR implementado y probado con GitHub simulado.
- [x] Suite local aislada de 264 pruebas aprobada y CI del codigo d29e17b aprobada.

La generacion real validada fue una prueba sintetica; no fue disparada por un
mensaje del participante. El publicador aun no ha creado un PR real.

## Siguiente implementacion: conectar WhatsApp con el agente

- [ ] Despachar a Actions las solicitudes guardadas, con reintentos y deduplicacion.
- [ ] Autenticar la consulta de solicitudes y sus actualizaciones de estado.
- [ ] Ejecutar una solicitud real con IA, normalizacion y validacion aislada.
- [ ] Devolver preguntas de aclaracion por WhatsApp y continuar con la respuesta.
- [ ] Crear el primer PR real a partir del candidato validado.
- [ ] Proteger main, exigir controles y revalidar base y contenido antes de integrar.
- [ ] Desplegar el commit integrado, confirmar salud/version y gestionar fallos.
- [ ] Responder por WhatsApp con PR, pruebas y version publicada.

## Segundo reto y entrega

- [ ] Activar revision tras el push de un desarrollador autorizado.
- [ ] Reportar convenciones con archivo/linea y preparar correcciones, evitando bucles.
- [ ] Demostrar ambos recorridos, concurrencia y fallos con evidencia.
- [ ] Completar guion de demostracion y defensa academica.
- [ ] Resolver el uso del token temporal de WhatsApp para evitar renovaciones imprevistas.

## Donde revisar la evidencia

- [Historial de codigo](https://github.com/Sebitafx/agentops-tareas/commits/main/).
- [Todas las ejecuciones de Actions](https://github.com/Sebitafx/agentops-tareas/actions).
- [Ultima CI del codigo d29e17b](https://github.com/Sebitafx/agentops-tareas/actions/runs/41749200772).
- [Propuesta real validada al primer intento](https://github.com/Sebitafx/agentops-tareas/actions/runs/41747916063).
- [Aplicacion publicada](https://agentops-tasks.onrender.com/).
- [Evidencias detalladas](evidencias.md).

Actions muestra queued/in progress cuando existe una ejecucion activa y completed
cuando termino. Las respuestas del chat o este checklist no crean un trabajo por
si solos. El receptor publicado aun informa agents pending: no procesa correcciones.
