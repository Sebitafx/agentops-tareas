# Comprobar Groq como alternativa

El participante eligio probar Groq tras un timeout de red de Gemini y guardo una
clave dedicada como repository secret `GROQ_API_KEY`. El fallo de Gemini no demuestra
cuota agotada ni saturacion. Mantener su control independiente para diagnosticarlo despues.

## Ejecucion

GitHub > Actions > **Groq API check** > Run workflow > main. La primera subida del
archivo de workflow a main tambien ejecuta el control, al igual que cambios en el
control Groq o su transporte. No se activa desde PR,
forks ni ramas distintas de main. No usa ni extrae credenciales locales de Git.
Para repetir un job fallido usar la UI de GitHub o un conector autorizado para Actions.

Se consulta `GET https://api.groq.com/openai/v1/models` para confirmar que aparece
activo `openai/gpt-oss-120b`. Solo entonces se envia un POST a `/chat/completions`
con el texto sintetico `Reply with exactly OK.`, salida maxima de 1024 tokens y
razonamiento bajo. No se incluyen tools, busqueda, datos de Neon, mensajes de
WhatsApp ni codigo del repositorio. No se ejecuta la respuesta del modelo.

El transporte compartido admite unicamente HTTPS y los hosts revisados de Google
y Groq. Identifica el cliente como AgentOps-Tareas con su URL de repositorio mediante
User-Agent. La prueba publica sin claves rechazo el cliente predeterminado con 403
y acepto la solicitud del cliente identificado hasta el control de autenticacion (401).
Esta prueba de transporte no verifica por si sola la clave real.

El transporte no sigue redirects, no reintenta errores y acota la respuesta a 1 MiB. No
imprime claves, cuerpos de respuestas, razonamiento ni errores crudos del proveedor.

Resultado exitoso esperado:

```json
{
  "status": "ok",
  "provider": "groq",
  "model": "openai/gpt-oss-120b",
  "model_access": true,
  "generation_confirmed": true,
  "billing_verified": false,
  "remaining_quota": "unknown"
}
```

Esto acredita una generacion real, no un saldo de cuota, plan gratuito verificado
automaticamente ni calidad al corregir codigo. Mantener el Free Plan en Groq y
comprobar los limites reales de la organizacion. No activar Developer ni pagos
para resolver un 429. La respuesta 429 se informa como QUOTA_OR_RATE_LIMIT;
un 401/403 requiere revisar la clave y permisos; NETWORK_ERROR indica un problema
de conectividad sin demostrar fallo de autenticacion.

No hay fallback automatico entre proveedores ni cambios de modelo silenciosos.
Despues de validar acceso se evaluaran errores pequenos de Python antes de permitir
que un modelo proponga cambios de codigo. Actualizar e informar sobre el tratamiento
de mensajes con IA antes de enviar contenido real: la politica publica actual solo
cubre almacenamiento y pruebas sin IA sobre mensajes de WhatsApp.

Fuentes primarias:

- [Modelo GPT OSS 120B en Groq](https://console.groq.com/docs/model/openai/gpt-oss-120b)
- [Referencia API](https://console.groq.com/docs/api-reference)
- [Razonamiento y parametros](https://console.groq.com/docs/reasoning)
- [Limites Free Plan](https://console.groq.com/docs/rate-limits)
