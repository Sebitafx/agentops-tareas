# Validar la GitHub App dedicada

App registrada e instalada por el participante: `agentops-tareas-sebitafx`.
App ID: `5601084` (identificador, no secreto). Los permisos configurados son
Contents, Pull requests y Actions en lectura/escritura, mas Metadata en lectura.
La App no necesita webhook: los eventos de push los recibiran los workflows.

Los secretos AGENT_APP_ID y AGENT_APP_PRIVATE_KEY se guardaron en Actions. No se
debe leer la clave privada desde chats, repositorio ni credenciales personales.

## GitHub App check

El workflow se ejecuta en main al crear/modificar su archivo o el comprobador, y
manualmente desde Actions. No usa secretos en PR ni forks.

1. La accion oficial actions/create-github-app-token@v3 crea un token solo de
   lectura de Metadata para listar el alcance de la instalacion en Sebitafx.
2. El comprobador exige la identidad de nuestra app y exactamente un repositorio
   accesible: Sebitafx/agentops-tareas. Si hay mas, detener y corregir Repository access.
   Esta lectura acredita el alcance actual; mantener Only select repositories en
   la instalacion para no incorporar automaticamente futuros repositorios.
3. Solo si el alcance es correcto, se solicita un segundo token limitado a ese repo,
   con Contents, Pull requests y Actions write. Su emision falla si la instalacion
   no concede los permisos solicitados.
4. Con el segundo token se hacen consultas GET de repo, main, PR y workflows.
   No se crean ramas, commits, PR, comentarios, dispatches ni despliegues en esta prueba.
5. La accion oficial revoca ambos tokens al terminar el job; no se desactiva ese paso.

La emision del token verifica permisos concedidos y los GET prueban acceso de
lectura. No demuestra aun una operacion de escritura: el resultado dice
`write_operations_tested: false`. La prueba real de ramas/PR se hara con el arnes y
las validaciones de cambios. Esto no configura proteccion de main por si solo.

La clave privada se entrega solo a la accion oficial y los tokens solo a los pasos
que los necesitan. Los errores de gh se capturan sin imprimir respuestas crudas,
tokens, datos de otros repositorios ni stderr. GH_TOKEN debe estar definido;
el comprobador no recurre a autenticacion personal o al credential manager.

Si falla la autenticacion, revisar App ID, archivo PEM completo y que la instalacion
este activa. Si el alcance no coincide, modificar la instalacion para seleccionar
unicamente agentops-tareas. No ampliar permisos para ocultar errores del control.

Referencias:

- https://github.com/actions/create-github-app-token
- https://docs.github.com/en/rest/apps/installations
