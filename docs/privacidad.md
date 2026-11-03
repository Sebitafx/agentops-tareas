# Publicacion de las paginas informativas

El responsable autorizo publicar `oriundotafur@gmail.com` como contacto de privacidad.
Revisar `/privacy` y `/data-deletion` antes de configurar las URLs en Meta. Son paginas
publicas sin autenticacion, independientes de la base de datos y del estado del receptor.
No contienen credenciales ni informacion de participantes.

En Meta > Configuracion de la aplicacion > Informacion basica:

- Politica de privacidad: `https://agentops-receiver.onrender.com/privacy`.
- Si solicita instrucciones de eliminacion: `https://agentops-receiver.onrender.com/data-deletion`.
  Seleccionar URL de instrucciones, no callback automatico. No hay callback de borrado implementado.

Las URLs solo sirven despues de desplegar esta version y comprobar que responden 200.
No aseguran aprobacion de Meta: revisar los siguientes requisitos del panel.

## Atender una solicitud de eliminacion

La administracion verifica en privado que el solicitante controla el numero del
participante. No solicitar contrasenas, OTP ni documentos. No publicar solicitudes
de privacidad en GitHub. Si el usuario pide dejar de participar, quitar su numero
de WHATSAPP_ALLOWED_SENDERS y aplicar los cambios antes de eliminar registros.
Para el ultimo participante, dejar la lista vacia deshabilita la recepcion.

Desde el SQL Editor privado de Neon, en una transaccion, eliminar primero los
estados cuyo message_id corresponda a los mensajes del remitente y luego los
registros de agentops_inbox de ese remitente. Filtrar siempre por el numero
verificado, nunca eliminar otras filas. Confirmar los contadores sin exportar
mensajes y responder al solicitante. Las notificaciones de entrega independientes
no contienen numero personal y pueden no ser asociables al participante.

Esta version no realiza limpieza automatica. Si se habilitan IA, exportaciones,
nuevos tipos de datos o una politica de retencion automatica, actualizar estas
paginas y el procedimiento antes de activar ese tratamiento.
