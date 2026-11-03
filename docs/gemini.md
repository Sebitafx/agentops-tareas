# Verificar Gemini desde GitHub Actions

## Configuracion

1. Mantener el proyecto de Google AI Studio en el nivel gratuito, sin activar facturacion.
2. Crear una clave dedicada y guardarla en GitHub > Settings > Secrets and variables >
   Actions > Repository secrets, con nombre `GEMINI_API_KEY`.
3. Ejecutar **Gemini API check** desde Actions > Run workflow > rama main.

La primera subida de este workflow a main tambien lo ejecuta. Despues solo se
activa manualmente o si se modifica su archivo, no con cada cambio de la app.
No se ejecuta desde PR, forks ni ramas distintas de main. El token de GitHub es de
solo lectura y checkout no persiste sus credenciales.

## Que se prueba

El control usa solo Python estandar y el secreto dentro del runner. Hace como maximo
un GET de metadatos y un POST generateContent, sin reintentos ni fallback. El modelo
inicial es `gemini-3.8-flash`, documentado con nivel gratuito al preparar el control.
No se permite cambiar a un modelo no revisado desde variables o parametros.

Prompt sintetico: `Reply with exactly OK.`. La salida se limita a 1024 tokens con
thinking bajo. No hay tools, ejecucion de codigo, busqueda, mensajes de WhatsApp,
conexion a Neon ni contenido del repositorio enviado al modelo.

El control no imprime la clave ni la respuesta cruda, y no sigue redirects que
puedan reenviar el header de autenticacion. Solo imprime un resumen JSON acotado.
No hay archivo de secretos ni artefactos que contengan respuestas.

Un resultado `status: ok` confirma acceso al modelo y una generacion real, en ese
momento. **No certifica el plan de facturacion, la cuota restante ni la calidad de
correcciones de codigo.** El campo `billing_verified: false` expresa esa limitacion.
Confirmar el nivel gratuito en el panel de Google; el control no cambia su facturacion.
Los 429 se detienen: no activan pago ni cambio automatico de proveedor/modelo.

| reason | Interpretacion |
|---|---|
| MISSING_OR_INVALID_API_KEY | Falta el secreto o tiene espacios/saltos de linea. |
| MODEL_UNAVAILABLE | El modelo no esta disponible en esa ruta/cuenta; revisar catalogo antes de cambiarlo. |
| AUTHENTICATION_FAILED / PERMISSION_DENIED | Revisar validez, restricciones, permisos y proyecto de la clave. |
| QUOTA_OR_RATE_LIMIT | Cuota o limite alcanzado; un solo fallo no permite saber si es temporal o cuota cero. |
| INVALID_REQUEST | La API rechazo la peticion; revisar compatibilidad y configuracion sin publicar datos crudos. |
| NETWORK_ERROR / PROVIDER_UNAVAILABLE | Problema de red o proveedor; repetir manualmente cuando se resuelva. |
| GENERATION_NOT_CONFIRMED | No se obtuvo la confirmacion esperada; no declarar prueba exitosa. |

Documentacion primaria:

- [Modelos y metadatos](https://ai.google.dev/api/models)
- [Generacion de contenido](https://ai.google.dev/api/generate-content)
- [Modelo inicial](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
- [Precios y modalidad gratuita](https://ai.google.dev/gemini-api/docs/pricing)
- [Google AI Pro y la API se gestionan por separado](https://ai.google.dev/gemini-api/docs/google-ai-plans)

La privacidad de WhatsApp permanece igual: este control solo envia texto sintetico.
Antes de procesar mensajes reales con IA hay que actualizar el aviso e informar a los participantes.
