# Explicacion y defensa academica

## Presentacion breve

Construimos un gestor de tareas y dos recorridos de automatizacion. El primero
recibe una peticion por WhatsApp y prepara un cambio de codigo. El segundo revisa
un push de un desarrollador contra nuestras convenciones Python. Ambos usan un
modelo para proponer o revisar y un arnes que decide que se permite ejecutar.

El resultado esperado no es un texto que dice haber arreglado algo: es un PR
trazable, controles aprobados, un commit publicado y su version comprobada.
Separar en la exposicion lo demostrado realmente y lo probado con simulaciones.

## Componentes y responsabilidades

1. Meta entrega eventos al receptor FastAPI mediante HTTPS. Validamos firma HMAC,
   remitente y numero destino, y guardamos antes de confirmar el webhook.
2. PostgreSQL conserva mensajes, solicitudes y respuestas pendientes. La base
   persiste aunque un contenedor de Render se reinicie o se redespliegue.
3. El despachador pide a GitHub Actions ejecutar un trabajo por UUID. El texto
   personal se consulta por una API privada; no se publica como input del workflow.
4. El controlador selecciona contexto publico, llama Groq y valida un contrato JSON.
   El modelo puede cambiar, pedir aclaracion o rechazar dentro de limites concretos.
5. El arnes controla rutas, hashes, numero de intentos y herramientas. Ruff normaliza
   texto Python; Docker ejecuta controles predefinidos sobre el candidato aislado.
6. La GitHub App crea rama y PR. El integrador exige proteccion, CI y SHA exactos.
7. Render recibe un hook con el commit integrado. El controlador confirma version,
   salud y base de datos; solo entonces informa succeeded por la cola de WhatsApp.

El revisor comparte los pasos de validacion, PR e integracion; cambia su disparador
y agrega hallazgos de reglas Python y recomendaciones contextuales.

## Conceptos que conviene defender

**Agente:** combina entrada, decision del modelo, herramientas, retroalimentacion
y condicion de parada. Una respuesta de ayuda es una funcion determinista y no
necesita IA. Guardar una solicitud tampoco prueba que un agente la haya completado.

**Arnes (harness):** es el codigo confiable que rodea al modelo. Valida su salida,
limita operaciones y presupuesto, ejecuta herramientas y decide continuar o detenerse.
El prompt ayuda a orientar; los controles de codigo y del contenedor hacen cumplir limites.

**Herramientas:** lectura acotada de archivos, propuesta estructurada, normalizacion
Ruff, validacion Docker y publicacion GitHub. El modelo no escoge comandos shell
libres ni recibe credenciales. El coordinador usa secretos fuera del contenedor.

**CI/CD:** CI comprueba cada cambio. CD publica una version que supero los controles.
La proteccion de main impide saltarse el PR. El SHA relaciona el codigo probado,
el merge y la version que devuelve el servicio.

**E2E:** Chromium interactua con la interfaz y la API real de una instancia local,
con PostgreSQL de prueba. Ademas existe un recorrido local del broker con Docker
real y proveedores simulados. Ninguno sustituye WhatsApp real y despliegue en nube.

**Servicios y microservicios:** separamos receptor y aplicacion por responsabilidad
y secretos. Comparten PostgreSQL para simplificar la demo; no presentamos esa base
compartida como independencia total de microservicios. Kubernetes no es necesario
para demostrar los retos: Render ejecuta los contenedores.

**Idempotencia:** el id de Meta evita duplicar la entrada; claim y lease evitan
ejecuciones dobles; event_key evita duplicar callbacks. No prometemos exactly once
al enviar a Meta: un timeout puede dejar entrega incierta y exige revision.

## Preguntas posibles

- ¿Por que el modelo no despliega directamente? Porque proponer y autorizar una
  publicacion son responsabilidades distintas; los controles verifican evidencia.
- ¿Como evitan bucles? Ramas agentops excluidas del reparador y actor autorizado;
  la CI valida al bot, pero no inicia otra reparacion del bot.
- ¿Que pasa si dos solicitudes llegan juntas? Se guardan ambas; claims atomicos,
  despacho serializado y grupo comun de concurrencia limitan integraciones simultaneas.
- ¿Y si la IA se equivoca tres veces? Se detiene y registra fallo, sin declarar exito.
- ¿Y si cambia main? Se detiene por base obsoleta; hay que repetir para validar
  contra la base actual. Esta version no reanuda automaticamente ese conflicto.
- ¿Como funciona la restauracion? Intenta desplegar el commit anterior y comprobarlo.
  No deshace migraciones ni datos; el agente no puede proponer migraciones.
- ¿Son suficientes los tests? No garantizan correccion universal ni ausencia de
  vulnerabilidades. El alcance reducido y aislamiento limitan consecuencias, y
  los benchmarks comparan requisitos con comportamientos independientes del modelo.
- ¿Es gratis sin limites? No. Cuotas de IA, arranques en frio y horas de Render
  condicionan la demostracion. Google Pro no se asume credito de API.

## Evidencia para exponer

Mostrar en este orden: peticion o push, UUID/SHA, workflow, diagnostico y pruebas,
PR, commit integrado, /version, cambio visible y respuesta final. Conservar
enlaces y ocultar secretos y datos personales en capturas. Ver [demo](demo.md).
