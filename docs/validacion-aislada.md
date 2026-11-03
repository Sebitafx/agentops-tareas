# Validacion real en Docker

Dockerfile.validation construye una imagen de referencia con herramientas, pruebas,
Chromium y PostgreSQL. La instalacion puede acceder a Internet durante la construccion;
la ejecucion de pruebas del candidato tiene --network none y no recibe credenciales.
Es una imagen diferente de la imagen pequena que se despliega en Render.

DockerValidator lee solo app y tests seguidos por Git, preserva sus bytes, rechaza
symlinks y prepara una copia temporal. No sobreescribe el checkout. Los cambios
deben pasar la politica de archivos; tampoco puede eliminar pruebas ni alterarlas.
El contenedor vuelve a comparar las pruebas existentes con la referencia de la imagen.

El contenedor corre como UID 10001, raiz de solo lectura, sin capabilities, con
no-new-privileges y un unico montaje del candidato en modo readonly. No se monta
docker.sock, el directorio del usuario ni los archivos .env. Solo /tmp es escribible.
Limites: 1.5 GiB de memoria, 2 CPU, 256 procesos/hilos, /tmp de 768 MiB, 10 segundos
para comandos de limpieza y 240 segundos de validacion. Un timeout elimina su
contenedor. La salida al coordinador se limita a 1 MiB y cada diagnostico a 6000
caracteres; el modelo recibe como maximo 4000 de feedback.

offline_runner comprueba red solo con loopback, usuario sin privilegios y raiz
readonly. Inicializa una base ficticia agentops_test mediante socket Unix dentro
del mismo contenedor. Chromium y FastAPI pueden comunicarse por loopback; no existe
una interfaz de red externa ni acceso a Neon. Ruff, formato, mypy y pytest con
cobertura >=80% y E2E son comandos predefinidos, no instrucciones del modelo.

La aprobacion requiere salida cero, banderas de aislamiento correctas y todos los
controles esperados aprobados. Un reporte incompleto, salida invalida o timeout no
aprueba. artifacts/latest-validation.json permite revisar etapas y diagnosticos.
Bootstrap CI ahora usa esta misma ruta; no ejecuta pytest de los candidatos en el host.

Para desarrollo local, desde el repo en una revision conocida, construir la imagen
con tag agentops-validator:SHA_COMPLETO mediante docker build --file Dockerfile.validation.
Despues ejecutar python -m harness.sandbox --image agentops-validator:SHA_COMPLETO.
Los nombres de imagen aceptados son fijos y las rutas del montaje se validan.

El aislamiento reduce el alcance del codigo propuesto. No certifica ausencia de
vulnerabilidades del sistema, correccion mas alla de las pruebas ni inmunidad a
intentos de manipular el evaluador. La integracion y el despliegue necesitan ademas
comprobar PR, base y SHA, mantener main protegida y confirmar la version publicada.

Referencias oficiales:
- [Opciones de docker run](https://docs.docker.com/reference/cli/docker/container/run/).
- [Almacenamiento tmpfs](https://docs.docker.com/engine/storage/tmpfs/).
