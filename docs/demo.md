# Guion de demostracion

Antes: CI aprobada, proteccion y variables de activacion-final.md, /ready correcto,
token de WhatsApp vigente y servicios despiertos. No iniciar una nueva peticion
hasta ver el resultado de la anterior. Tiempo de compilacion y cuota pueden variar.

## Reto 1

1. Enviar ayuda, ¿qué puedes hacer? y ver estos comandos. Deben dar ayuda sin
   crear un trabajo de cambio. Probar estado sin id y estado invalido.
2. Enviar: Cambia el texto del boton Crear tarea por Agregar tarea. Conserva el
   comportamiento al guardar y el texto Guardar cambios al editar.
3. Guardar UUID. Mostrar Actions → WhatsApp agent y el PR. Esperar resultado:
   pr_open no significa desplegado; succeeded exige comprobacion de version.
4. Abrir la web, crear/editar una tarea ficticia, confirmar etiqueta nueva incluso
   despues de guardar. Comparar /version con el commit de merge y respuesta final.
5. Ambiguedad: Cambia un boton. Debe preguntar que boton y como cambiarlo, sin PR.
   Responder: El boton de crear; cambia Agregar tarea por Crear tarea y conserva CRUD.
   Confirmar que se retoma el mismo UUID con nuevo workflow.
6. Funcion nueva: Agrega un buscador local por titulo, sin distinguir mayusculas.
   Usa id task-search y etiqueta Buscar tareas. Al borrar la busqueda muestra todas
   las tareas del filtro actual. No cambies API ni base de datos.
   Crear Alfa y Beta, buscar ALFA, beTA y vaciar. Revisar los controles del PR.

Si el benchmark ya mostro dificultad o cuota agotada para el buscador, no ocultarlo:
mostrar el fallo seguro y renovar la prueba cuando la cuota permita. Ningun cambio
debe publicarse solo porque el bot diga que lo hizo.

## Reto 2

Crear rama desde main actual. Agregar taskapp/demo_conventions.py con una funcion
pequena nueva que no se importe desde el servidor. Primer caso: import sin usar y
funcion sin tipos. Hacer commit y push como Sebitafx. La CI general puede fallar
en esa rama: el revisor debe reportar regla/linea y preparar un PR correctivo limpio.

Mostrar Review developer push, artefacto push-review.json, comentario del PR y
controles aprobados tras la reparacion. Confirmar merge y /version. Luego repetir
desde main con otra funcion tipada, formateada y util: debe superar revision sin
reparacion. No modificar workflows, dependencias ni pruebas existentes en estas ramas.

## Persistencia y fallos

Crear una tarea ficticia identificable antes del redespliegue, verificar mismo id y
contenido despues. Eliminar solo los datos de la demo al terminar.

Los casos de firma invalida, duplicados, remitente no autorizado, doble claim,
fallos de tests, cuota y despliegue tienen pruebas reproducibles locales. Mostrar
el reporte indicando cuales usan APIs simuladas. No provocar fallos deliberados
con credenciales ni infraestructura del servicio publico.

## Registro minimo por caso real

Fecha/hora Lima, texto ficticio, UUID o SHA de push, enlace Actions, PR, SHA de
merge, /version observado, resultado y limitaciones. Agregar a evidencias.md;
no registrar numero personal, tokens ni cuerpo completo de eventos privados.
