# Arquitectura del sistema: dos agentes de desarrollo

Documento de referencia para la defensa. Describe como el mismo repositorio
satisface los dos retos: el agente que corrige y despliega a partir de un
reporte por WhatsApp, y el agente que revisa los pushes de un desarrollador.

## Vista general

```
                    ┌────────────────────────────────────────────────────┐
 Reto 1 (peticion)  │                  Reto 2 (supervision)              │
                    │                                                    │
 WhatsApp ──webhook──►  agentops-receiver    push (rama demo) ─┐           │
                firma │  rol receiver          ▼                │           │
                lista │  webhook durable       Review developer│           │
                remit.│       │                push (Actions)  │           │
                      │       ▼ dispatch (App)  revisor +      │           │
                      │  WhatsApp agent workflow   reparacion  │           │
                      │  harness.request_worker ──┐    │        │           │
                      │       │                   │    ▼        │           │
                      │       ▼                   │  PR correctivo          │
                      │  propuesta Groq ──────────┘                           │
                      │       │                                               │
                      │       ▼                                               │
                      │  validacion Docker aislada (sin red, sin secretos)    │
                      │       │                                               │
                      │       ▼ superada                                      │
                      │  publicar rama + PR ── merge (protegido) ── main      │
                      │       │                                │              │
                      │       ▼                                ▼              │
                      │  deploy hook ──► agentops-tasks (Render, Docker)      │
                      │                                        │              │
                      └────────────────────────────────────────────────────────┘
                      /version y /health /ready confirman el despliegue
```

## Componentes

| Componente | Rol |
|---|---|
| `taskapp/` | Aplicacion web CRUD de tareas (FastAPI + Jinja) sobre PostgreSQL. Los agentes solo pueden tocar este directorio y agregar pruebas en `tests/agent_added/`. |
| `bootstrap/` | Punto de entrada unico con roles por variable `SERVICE_ROLE`: `receiver` (webhook WhatsApp, cola de jobs, outbox de respuestas) y `tasks` (aplicacion publica + API privada). Un solo artefacto Docker, dos servicios en Render. |
| `harness/` | El arnes de los agentes (`code_proposer`, `engine`, `sandbox`, `offline_runner`, `proposals`, `review_push`, `request_worker`, `evaluation_check`). Define las herramientas, los limites y la evidencia obligatoria. |
| `tests/` | Pruebas de referencia (inmutables en el validador), pruebas E2E con Chromium real y pruebas unitarias, 321 casos con cobertura publica >= 80 %. |
| `.github/workflows/` | Orquestacion en la nube: `whatsapp-agent` (Reto 1), `review-push` (Reto 2), `agent-proposal-check` (evaluacion y benchmarks), `bootstrap-ci` (calidad), `github-app-check`/`groq-check` (preflight). |

## Recorrido del Reto 1: reporte por WhatsApp

1. El participante autorizado escribe la peticion. El receptor valida firma
   HMAC, remitente permitido y durabilidad: la solicitud se persiste en
   PostgreSQL con UUID antes de cualquier trabajo.
2. El estado se consulta por WhatsApp. Peticiones ambiguas generan una
   pregunta (`clarify`) sin crear cambios; comandos y preguntas de capacidad
   producen ayuda sin crear jobs.
3. El receptor despacha el job a `WhatsApp agent` (workflow_dispatch con
   `job_id`) usando la GitHub App instalada solo en este repositorio, con
   permisos Contents/PR/Actions de escritura y Administration de solo lectura.
4. `harness.request_worker` ejecuta el bucle acotado: Groq propone JSON
   (contrato `Proposal`), el normalizador revisa alcance, `harness.sandbox`
   valida la imagen candidata en un contenedor Docker real sin red, sin
   secretos y con pruebas de referencia inmutables.
5. Si la validacion pasa: publicacion de rama + PR con hashes de base
   comprobados (`STALE_BASE` evita bases desactualizadas), integracion con la
   proteccion de `main` (PR + `bootstrap-quality`), despliegue por deploy
   hook y comprobacion de `/version` y salud. Cualquier fallo se reporta por
   WhatsApp con el motivo. Maximo 3 intentos; un fallo no acumula cambios.

## Recorrido del Reto 2: supervision de pushes

1. El desarrollador hace push a una rama distinta de `main` y de `agentops/*`.
2. `Review developer push` revisa contra `main` con el mismo validador
   confiable: Ruff (estilo y lint), ruff format, mypy (tipos) y la suite en
   el contenedor aislado.
3. Un revisor explica los incumplimientos que requieren contexto
   (convencion vs regla mecanica), con archivo y linea, y prepara un PR
   correctivo limpio que vuelve a pasar todas las verificaciones.
4. La prevencion de bucles impide que dos agentes se corrijan entre si: las
   correcciones pasan controles pero no disparan otro proceso automatico.

## Barandillas de seguridad (donde mirar en la defensa)

- **Aislamiento**: validacion en Docker sin red (`network_none`), root
  de solo lectura, sin symlinks, limite de tamano de logs (`RLIMIT_FSIZE`),
  rechazo de secretos en el entorno del contenedor.
- **Presupuesto acotado**: maximo 3 intentos, 16000 caracteres de contexto
  para el modelo con recorte del diagnostico conservando codigo y requisito,
  maximo 4 archivos por propuesta, 65536 bytes de cambio, intervalo minimo de
  65 s entre llamadas para la cuota gratuita de Groq.
- **Contrato cerrado**: respuesta JSON estricta (`Proposal`), extra=forbid,
  ruta canonica sin escapes, sin binarios, archivos vacios ni reemplazo de
  pruebas de referencia; el codigo recibido nunca se ejecuta sin medir antes.
- **No filtrado**: `persist-credentials: false`, impresion de cuerpo de
  eventos prohibida, motivos publicos estables (`CheckError.reason`), claves
  solo como secretos de Actions o de Render.
- **Integracion segura**: proteccion de `main` clasica con PR obligatorio,
  check `bootstrap-quality`, ramas al dia, sin bypass de administrador y sin
  historial lineal para permitir merges de dos padres verificados.

## Mapa a los temas del curso

- Contenedores y orquestacion: cada validacion corre en contenedores reales
  construidos desde el mismo SHA; los roles y el despliegue se controlan por
  variables y hooks, como en Kubernetes (probes, restricciones de contexto,
  imagen versionada por SHA).
- Microservicios: un artefacto, varios roles con persistencia compartida y
  contratos explicitos (webhook durable, outbox, API privada de jobs).
- E2E: Chromium real contra la aplicacion desplegada; el flujo del Reto 1 es
  un E2E de negocio completo (Mensajeria → PR → despliegue → respuesta).
- Harness agent: el directorio `harness/` es literalmente la respuesta a este
  tema: herramientas acotadas, presupuesto de intentos y contexto, validacion
  separada del generador y evidencia por intento.
