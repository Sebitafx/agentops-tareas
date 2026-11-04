# Autenticacion del futuro despachador

bootstrap/github_app.py prepara la autenticacion de servidor mediante la GitHub App
dedicada. Aun no despacha solicitudes ni publica PR: falta conectar el cliente con
los trabajos y los workflows del agente.

AGENT_APP_ID y AGENT_APP_PRIVATE_KEY se leen solo del entorno. El cliente requiere
RSA de al menos 2048 bits y firma un JWT RS256 de corta duracion. Verifica el slug
agentops-tareas-sebitafx y busca su instalacion para Sebitafx/agentops-tareas.
Solicita un token de instalacion limitado a ese repositorio y a permisos declarados
por el coordinador. Intenta revocarlo al terminar, incluso si falla la operacion.
Un fallo de revocacion se registra sin secreto y no repite una escritura previa.

La clave permanece en memoria del servidor; el JWT y el token se envian solo como
cabecera a api.github.com. No hay credenciales personales de respaldo. El transporte
impide redirects, limita respuesta y timeout, y comunica errores con motivos
estables sin imprimir respuestas privadas.

control_token deriva un secreto separado por dominio a partir de la clave privada
normalizada a DER. Se reserva para autenticar futuras llamadas entre el workflow
confiable y el receptor, sin copiar otra variable. Aun no existe ese endpoint.
El mismo PEM debe estar configurado en ambos servicios. No entregar ese secreto
ni el PEM a los modelos, al codigo candidato o a su contenedor de pruebas.

Las pruebas generan claves ficticias y verifican firma, caducidad, normalizacion
entre formatos PEM, app inesperada, destino fijo y revocacion. No acreditan todavia
que este cliente Python autentique contra GitHub con la clave real de Render.

Referencias:
- [JWT de GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app).
- [PyJWT](https://pypi.org/project/PyJWT/).
