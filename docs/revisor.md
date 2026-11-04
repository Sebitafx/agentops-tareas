# Revisor de pushes

Review developer push se activa en ramas distintas de main y agentops/**, solo
para Sebitafx en este repositorio. La CI general valida tambien pushes y PR del bot.
Forks y actores ajenos no acceden a este workflow con secretos.

El controlador corre desde main confiable y lee el commit del desarrollador con
git show como datos; no hace checkout ni ejecuta sus comandos en el host.
Compara con main y solo admite taskapp y nuevas pruebas autorizadas, maximo cuatro
archivos y 64 KiB. Infraestructura y borrados requieren revision manual.

Primero valida sin reparar. Reporta reglas Ruff y errores mypy con archivo y linea;
para fallos generales conserva el diagnostico del control y referencia el archivo.
Si falla, permite tres reparaciones como maximo y vuelve a validar. Un fallo
persistente no genera un PR aprobado. Si la reparacion deja exactamente main,
informa already_satisfied sin crear un PR vacio.

La revision contextual de Groq agrega recomendaciones con ruta, linea y regla.
Estas recomendaciones no bloquean por preferencia subjetiva; las validaciones
deterministas si. Un proveedor inaccesible o respuesta invalida detiene la revision
contextual. No hay fallback silencioso.

El PR identifica SHA del push y workflow; su comentario detalla el reporte.
push-review.json conserva hallazgos y resultado tres dias. La integracion exige
main protegido, CI aprobada y SHA exactos. El despliegue confirma version, salud y tareas.

Si main cambia durante la revision, se detiene con REVALIDATION_REQUIRED. Repetir
el push desde la base actual para revalidar. No reanuda automaticamente ese conflicto.
