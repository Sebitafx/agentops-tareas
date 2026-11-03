# Convenciones verificables de AgentOps Tareas

Estas reglas definen el criterio del segundo reto; no las modifica el agente.

- Python 3.13. Formato Ruff, referencia de 100 columnas, imports ordenados y lint limpio.
- snake_case para funciones y variables; PascalCase para clases; constantes en MAYUSCULAS.
- Funciones de taskapp con tipos de entrada y retorno; mypy limpio sobre taskapp.
- API, validacion y persistencia separadas: main, schemas y repository.
- Consultas SQL parametrizadas. Los identificadores dinamicos solo salen de campos permitidos.
- Validar entradas en el servidor; 404 para recursos ausentes y 503 para almacenamiento
  no disponible. Nunca devolver errores crudos con secretos, host o contrasenas.
- Las funciones nuevas o correcciones deben preservar tests existentes y aportar una
  prueba de comportamiento cuando cambien logica. Cobertura Python combinada >=80%.
- Los cambios de UI deben superar el recorrido E2E pertinente. Texto del usuario no
  se interpreta como HTML.
- No claves, tokens, datos personales de participantes ni archivos .env en el repo.
- El agente solo podra cambiar la aplicacion y agregar pruebas autorizadas. Los
  workflows, migraciones, dependencias y estas convenciones quedan fuera de su alcance.

Las comprobaciones automaticas son vinculantes. Las observaciones contextuales
de IA deben indicar archivo, linea y regla; las preferencias subjetivas se reportan
como recomendaciones, no como fallos verificables.
