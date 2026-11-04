# Arnes de propuestas y limites

Un modelo propone cambios; el arnes decide que operaciones permite y cuando detenerse.
El modelo no recibe comandos de shell, claves, infraestructura ni libertad de modificar
el repositorio completo. El contrato, bucle y validador Docker estan implementados;
aun falta conectar la creacion de PR y los mensajes almacenados de WhatsApp.

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
Mode y contrato validado localmente. Limita contexto a 16000 caracteres y salida
a 3072 tokens. Estos topes no garantizan cuota disponible; 429 detiene el trabajo.
Fuente: [JSON de Groq](https://console.groq.com/docs/structured-outputs) y
[parametros de razonamiento](https://console.groq.com/docs/reasoning).

Agent proposal check ahora usa evaluation_check: pide una propuesta para una tarea
sintetica, cambiar el limite de titulo de 200 a 180 y agregar pruebas. Solo envia
schemas.py, un indice de rutas publicas y esa peticion ficticia. Verifica contrato,
rutas, hashes y limites; prueba el candidato en Docker y permite hasta tres intentos.
Guarda propuesta y evidencia como artefactos tres dias. No aplica el parche al
checkout, crea PR ni despliega. Tampoco procesa mensajes personales de WhatsApp.
El preflight anterior produjo status proposed sin ejecutar codigo; no confundir
esa evidencia con validated. El workflow tiene contents read y no recibe tokens de GitHub
App ni credenciales de base de datos o Render. Solo main del repositorio autorizado.
