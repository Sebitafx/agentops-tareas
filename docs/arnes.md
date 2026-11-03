# Arnes de propuestas y limites

Un modelo propone cambios; el arnes decide que operaciones permite y cuando detenerse.
El modelo no recibe comandos de shell, claves, infraestructura ni libertad de modificar
el repositorio completo. Esta etapa introduce el contrato y el bucle; aun falta conectar
el validador Docker, la creacion de PR y los mensajes almacenados de WhatsApp.

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

El estado validated solo se obtiene del validador suministrado. Hoy los tests del
motor usan validadores simulados: no acreditan ejecucion aislada de codigo de IA.
Antes de conectar el motor a solicitudes reales, ese validador debe ejecutar los
controles predefinidos en Docker sin secretos ni acceso de red, conservar las pruebas
de referencia y producir evidencia verificable. La politica de rutas y el prompt
no son un aislamiento de seguridad ni demuestran correccion funcional.

## Adaptador y prueba real separada

GroqProposer usa el modelo comprobado openai/gpt-oss-120b, esfuerzo low, JSON Object
Mode y contrato validado localmente. Limita contexto a 16000 caracteres y salida
a 3072 tokens. Estos topes no garantizan cuota disponible; 429 detiene el trabajo.
Fuente: [JSON de Groq](https://console.groq.com/docs/structured-outputs) y
[parametros de razonamiento](https://console.groq.com/docs/reasoning).

Agent proposal check solicita una sola propuesta para una tarea sintetica: cambiar
el limite de titulo de 200 a 180 y agregar pruebas. Solo envia schemas.py y esa
peticion ficticia. Verifica contrato, rutas, hashes y limites; guarda el JSON como
artefacto de Actions durante tres dias. No aplica el parche, ejecuta codigo generado,
crea PR ni despliega. Tampoco procesa mensajes personales de WhatsApp.
Un resultado proposed acredita una generacion utilizable por el arnes, no un cambio
funcionalmente validado. El workflow tiene contents read y no recibe tokens de GitHub
App ni credenciales de base de datos o Render. Solo main del repositorio autorizado.
