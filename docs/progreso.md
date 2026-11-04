# Progreso verificable de los retos

Actualizado el 3 de noviembre de 2026, hora de Lima. Checklist manual: no ejecuta
trabajo en segundo plano. Implementacion, validacion local y demostracion en la
nube son evidencias diferentes.

## Comprobado en la nube

- [x] CRUD publico con PostgreSQL, filtros y API en agentops-tasks.
- [x] Recepcion real de WhatsApp, firma, lista de remitentes y persistencia en Neon.
- [x] Respuesta real de saludo/ayuda, registro de solicitudes y consulta de estado.
- [x] Propuesta real de Groq validada en Docker, sin PR ni despliegue.
- [x] CI aprobada del puente WhatsApp → Actions, commit daee926.

[CI daee926](https://github.com/Sebitafx/agentops-tareas/actions/runs/41758314695).
[Evaluacion real anterior](https://github.com/Sebitafx/agentops-tareas/actions/runs/41747916063).
El receptor mostrado por el participante sigue en la version de respuestas;
no hay evidencia aun de que ejecute el puente actualizado.

## Implementado localmente, pendiente de publicar esta iteracion

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
- [ ] Publicar el commit final y comprobar CI y benchmarks reales en Actions.

## Configuracion de cuentas

- [x] GitHub App instalada solo en este repositorio; secretos de Actions configurados.
- [x] Variables de App en el receptor y hook de tareas en Actions configurados por el participante.
- [x] Administration Read-only agregado segun confirmacion del participante;
      pendiente de comprobar su emision de token desde Actions.
- [ ] Proteger main: PR obligatorio, bootstrap-quality, base actualizada, sin bypass.
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
