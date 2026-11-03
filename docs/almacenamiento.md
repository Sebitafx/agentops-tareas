# Conectar Neon y verificar la bandeja de entrada

## Desplegar

1. Configurar `DATABASE_URL` en Render con la URL PostgreSQL completa de Neon.
   Conservar `sslmode=require` y `channel_binding=require`. No pegar un comando
   `psql`, comillas externas ni asteriscos. El pooling de Neon es compatible.
2. Cuando GitHub Actions apruebe este commit, Render > Manual Deploy > Deploy latest commit.
3. Abrir `/version` y comprobar el nuevo SHA. Abrir `/ready`.
4. Resultado esperado: `database: ok`, `schema_version: 001_inbox.sql`,
   `receiver_configured: false` y `agents: pending`.
5. Si devuelve 503, revisar variables y desplegar de nuevo. Los logs omiten datos
   de conexion; no publicar la URL, contrasena ni capturas de valores secretos.

## Habilitar recepcion

Guardar estas variables en Render antes de suscribir `messages` en Meta:

| Variable | Valor |
|---|---|
| `META_APP_SECRET` | Secreto de la aplicacion Meta, desde Configuracion > Informacion basica. No es el token de acceso ni META_VERIFY_TOKEN. |
| `WHATSAPP_PHONE_NUMBER_ID` | Phone Number ID del numero de prueba; no es el telefono ni el ID de cuenta de mensajes. |
| `WHATSAPP_ALLOWED_SENDERS` | Tu numero personal completo con codigo de pais, solo digitos; varios se separan por comas. |

Despues de guardar y reiniciar/desplegar, `/ready` debe mostrar
`receiver_configured: true`. Esto comprueba presencia y formato de la configuracion,
no acredita por si solo que el secreto sea correcto ni que Meta este entregando eventos.

El receptor valida `X-Hub-Signature-256` sobre los bytes originales, rechaza firmas
invalidas (403), limita entregas a 256 KiB y valida su estructura (400).
Acepta texto del numero de prueba y remitentes autorizados. Otros remitentes,
numeros, tipos multimedia y campos no relacionados se ignoran sin crear trabajos.
Las actualizaciones de entrega se guardan aparte y no se convierten en solicitudes.
No se guardan perfiles, contactos ni el payload completo. No se registran cuerpos
de mensajes o tokens. El access log se desactiva para no registrar el token del GET
de verificacion en su query string.

## Comprobar persistencia en Neon

Desde SQL Editor, consultas sin revelar telefonos ni textos:

```sql
SELECT version, applied_at FROM agentops_schema_versions;
SELECT state, count(*) FROM agentops_inbox GROUP BY state;
SELECT status, count(*) FROM agentops_delivery_status GROUP BY status;
```

Enviar una prueba firmada desde Meta y comprobar el contador. Repetir el mismo
evento conserva una sola fila por `message_id`. Reiniciar Render y comprobar que
las filas siguen presentes. El contenido de una prueba de Meta puede usar un
remitente ficticio: si no esta autorizado, no se guardara, por diseno. No desactivar
la firma ni abrir la lista de remitentes para hacer que una prueba pase.

Recepcion no implica respuesta ni ejecucion del agente: los mensajes quedan
`pending` hasta implementar el siguiente componente. El token de acceso de
WhatsApp sera necesario para enviar respuestas, no para esta bandeja.

## Pruebas locales y CI

Las pruebas de integracion usan `TEST_DATABASE_URL` y exigen una base llamada
`agentops_test`. No usar la base de Neon de la demo para ejecutar pruebas.
GitHub Actions inicia PostgreSQL 16 aislado, ejecuta pruebas con cobertura >=80%
y construye la imagen Docker. Sin TEST_DATABASE_URL las pruebas de integracion
se omiten explicitamente; no cuentan como validacion de PostgreSQL.

Administracion por CLI, solo en un entorno con DATABASE_URL configurada:

```text
python -m bootstrap.manage check
python -m bootstrap.manage migrate
python -m bootstrap.manage summary
```

`summary` solo imprime un contador. El resultado no debe confundirse con el estado
de un despliegue o una ejecucion de agentes.
