# Matriz de validacion

La suite aislada ejecuta PostgreSQL real y Chromium local. Los proveedores externos
se simulan en tests unitarios; la evaluacion de IA real se ejecuta aparte en Actions.

| Caso | Comprobacion | Alcance |
| --- | --- | --- |
| CRUD, filtros, recarga, movil y XSS | test_tasks_e2e.py + API | DB y navegador reales |
| Firma invalida, remitente ajeno, payload grande | test_receiver.py | Webhook local |
| Duplicados y persistencia atomica | Database/ReplyStore | PostgreSQL real |
| Ayuda natural y estado privado | respuestas/jobs | Sin IA |
| Aclaracion del mismo remitente | test_jobs.py | Mismo UUID, nuevo lease |
| Concurrencia y doble claim | test_jobs.py | Un workflow reclama el trabajo |
| Cuota/timeout/JSON invalido de IA | proveedor/motor | Simulados, limites comprobados |
| Prueba fallida o parche prohibido | motor/propuestas/sandbox | Sin PR aprobado |
| SHA movido, CI fallida y proteccion | test_delivery_pipeline.py | GitHub simulado |
| Despliegue fallido y restauracion | test_delivery_pipeline.py | Render simulado |
| Push valido, reparable e irreparable | test_review_push.py | APIs simuladas |
| Webhook → DB → API privada → Docker → callbacks | test_broker_e2e.py | Docker/PG/Chromium reales; IA/GitHub/Render simulados |
| Limite, texto, buscador y aclaracion | Agent proposal check | IA real + Docker, sin PR ni despliegue |

## Recorrido local del broker

Usar una base de prueba llamada agentops_test, nunca Neon de la demo. Crear la imagen
con el comando del README y configurar TEST_DATABASE_URL para esa base.

```powershell
$env:BROKER_E2E = '1'
$env:BROKER_VALIDATOR_IMAGE = "agentops-validator:$sha"
.venv/Scripts/python -m pytest -q tests/test_broker_e2e.py
```

Ese test se omite dentro del contenedor para evitar Docker anidado. Los tres tests
de test_acceptance_samples.py se omiten en CI base: se activa cada uno al validar
su propuesta de benchmark con VALIDATION_SCENARIO controlado por el coordinador.
Son pruebas de referencia; el modelo no puede reemplazarlas.

El E2E general usa #submit para no fijar la etiqueta del boton que la demo solicita
cambiar. Conserva todas las operaciones y aserciones CRUD. El benchmark comprueba
la nueva etiqueta incluso despues de guardar, evitando aprobar un cambio solo en HTML.
Se tolera la flecha decorativa del boton y se selecciona el textbox por rol para no
confundirlo con un contenedor search que tenga la misma etiqueta accesible.

## Evidencia pendiente en la nube

Mensaje real → workflow → PR → merge → /version → respuesta final; aclaracion real;
push correctivo real; persistencia despues de redesplegar. No marcar estos casos
aprobados por simulacion. Registrar enlaces y SHA en evidencias.md tras observarlos.
