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
