# Arnes de propuestas y limites

Un modelo propone cambios; el arnes decide que operaciones permite y cuando detenerse.
El modelo no recibe comandos de shell, claves, infraestructura ni libertad de modificar
el repositorio completo. El contrato, bucle, Docker y publicador estan conectados
con los mensajes almacenados; la evidencia real de cada recorrido se registra aparte.

## Contrato

Proposal contiene action change/clarify/refuse, resumen y hasta cuatro archivos.
Una aclaracion exige pregunta y no permite archivos. El cambio devuelve el contenido
completo, ruta relativa y SHA256 original de cada archivo; null significa nuevo.
Pydantic rechaza propiedades adicionales y estructuras invalidas.

El control de alcance permite archivos Python/HTML/CSS/JS de taskapp y pruebas
nuevas tests/agent_added/test_*.py. No admite reemplazar ninguna prueba existente,
incluidas las agregadas por ejecuciones anteriores. Prohibe cambios en bootstrap,
harness, workflows, migraciones, dependencias, configuracion y convenciones.
No existe una operacion de borrado. Rechaza rutas ambiguas, escapes, duplicados,
contenido binario/vacio, propuestas sin cambios y mas de 64 KiB por propuesta.

El hash debe coincidir con la base que vio el modelo. Es un control local de frescura,
no sustituye la comprobacion remota de base/head de PR antes de integrar.
Los archivos se combinan en una copia en memoria: no se escriben ni ejecutan.

## Bucle

run_request recibe proveedor y validador obligatorios. Cada intento usa la misma
base y recibe como maximo 4000 caracteres de diagnostico de la validacion anterior.
Una propuesta prohibida no llega al validador. No mas de tres intentos; las cuotas,
fallos del proveedor y validador no disponible detienen la solicitud. Un fallo nunca
devuelve un candidato aprobado. Clarificar o rechazar tambien detiene el trabajo.
Peticiones vagas conocidas, como Cambia un boton, se aclaran antes de llamar al
modelo para evitar que invente requisitos. Otras ambiguedades dependen del modelo.

Antes de validar, Ruff puede normalizar el texto de los archivos Python propuestos:
ordena imports y aplica formato mediante comandos fijos sobre stdin. Comprueba el
alcance antes y despues; no escribe el checkout, no importa la aplicacion y no
recibe secretos del coordinador. Los errores sintacticos siguen llegando al
validador; esta herramienta no convierte una prueba fallida en una aprobacion.

El estado validated solo se obtiene del validador suministrado. Los tests unitarios
del motor usan validadores simulados. DockerValidator es la implementacion real:
ver [validacion aislada](validacion-aislada.md). La politica de rutas y el prompt
no sustituyen el aislamiento ni demuestran correccion funcional por si solos.

## Adaptador y prueba real separada

GroqProposer usa el modelo comprobado openai/gpt-oss-120b, esfuerzo low, JSON Object
Mode y contrato validado localmente. Limita contexto a 19000 caracteres y salida
a 4096 tokens. Espera configurable entre llamadas (65 segundos en los workflows)
para reducir rafagas; no garantiza cuota disponible. Ante un 429 de Groq con
Retry-After numerico entre 0 y 60 segundos (sin incluir 0), el transporte espera
y reintenta la misma peticion hasta dos veces, como maximo 120 segundos de espera.
No reintenta errores de red, autenticacion ni otros proveedores. Si falta esa
cabecera, exige una espera mayor o persiste el rechazo, detiene el trabajo sin
cambiar modelo ni contratar servicios. Esto no elimina los limites diarios.
Ver [limites y cabeceras de Groq](https://console.groq.com/docs/rate-limits).
Fuente: [JSON de Groq](https://console.groq.com/docs/structured-outputs) y
[parametros de razonamiento](https://console.groq.com/docs/reasoning).

Agent proposal check se ejecuta solo manualmente (workflow_dispatch), para no
consumir cuota de IA automaticamente con cada cambio del arnes. Evitar iniciarlo
mientras hay solicitudes reales en curso: la cuota se comparte por organizacion.
Las validaciones obligatorias de Bootstrap CI siguen activas en push y PR.
Usa evaluation_check con cuatro escenarios: limite de titulo,
etiqueta de boton, buscador local y solicitud ambigua. Comparte solo los archivos
pertinentes y un indice publico. Verifica contrato, rutas, hashes y limites; prueba
el candidato en Docker y permite hasta tres intentos. Los tres cambios tienen
oraculos independientes en las pruebas de referencia; la ambiguedad exige clarify.
El caso ambiguo conocido usa la comprobacion previa de requisitos y no consume IA.
Guarda propuesta y evidencia como artefactos tres dias. No aplica el parche al
checkout, crea PR ni despliega. Tampoco procesa mensajes personales de WhatsApp.
El preflight anterior produjo status proposed sin ejecutar codigo; no confundir
esa evidencia con validated. El workflow tiene contents read y no recibe tokens de GitHub

## Respaldo Gemini ante cuota

Si GEMINI_API_KEY esta configurada en Actions, WhatsApp y la reparacion de pushes
usan Groq primero. Solo QUOTA_OR_RATE_LIMIT activa Gemini 3.5 Flash-Lite, con un evento
provider_fallback en el registro. No cambia por fallos de autenticacion, red,
contrato, politicas ni pruebas. Una vez activado, conserva Gemini durante los
intentos restantes de esa solicitud. No aumenta los tres intentos de correccion.
La revision contextual tambien admite ese respaldo, conservando su control de
reglas, archivos y lineas. Si ambos proveedores rechazan, se detiene sin aprobar.

Comparte el mismo contexto acotado, hashes y contrato Pydantic; exige respuesta
JSON completa del modelo permitido. Cada propuesta pasa las mismas politicas,
pruebas de referencia y contenedor aislado antes de crear un PR. La clave no
entra al prompt, contenedor ni artefactos. No se activa facturacion ni se infiere
cuota restante. Un plan gratuito puede seguir agotandose en ambos proveedores.
Las propuestas Gemini admiten hasta 8192 tokens de salida; la revision contextual
mantiene su limite menor. Una respuesta truncada sigue siendo rechazada.
Para modo oscuro se comparten HTML, JS y CSS completos, sin recortar codigo.

Gemini proposal check comprueba acceso y genera un cambio sintetico de etiqueta
con oraculo E2E; nunca crea PR ni despliega. Se puede lanzar manualmente en main.
Durante esta implementacion se ejecuta tambien al actualizar el adaptador en la
rama de mantenimiento explicitamente permitida, con actor/repo restringidos.
Ver [API Gemini](https://ai.google.dev/api/generate-content) y
[precios y modalidad gratuita](https://ai.google.dev/gemini-api/docs/pricing).
App ni credenciales de base de datos o Render. Solo main del repositorio autorizado.
