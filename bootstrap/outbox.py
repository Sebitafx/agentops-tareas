"""Recepcion y respuestas duraderas. No hay transacciones abiertas durante el envio."""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from psycopg.rows import dict_row

if TYPE_CHECKING:
    import psycopg

    from bootstrap.database import Database, IncomingMessage

APP_URL = "https://agentops-tasks.onrender.com/"
HELP = (
    "¡Hola! Soy AgentOps Tareas 🤖. Ya puedo recibir y responder por WhatsApp.\n\n"
    "Escribe una petición de cambio para registrarla, o usa:\n"
    "• ayuda: ver estos comandos\n• estado <id>: consultar una solicitud tuya\n\n"
    "El agente de corrección todavía está en conexión; aún no modifico ni despliego código.\n"
    "Aplicación de demostración: " + APP_URL
)


def is_help(text: str) -> bool:
    plain = "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )
    plain = " ".join(re.sub(r"[^a-z0-9 /]", " ", plain).split())
    return plain in {
        "hola",
        "hola agentops",
        "ayuda",
        "help",
        "inicio",
        "/start",
        "que puedes hacer",
        "que eres capaz de hacer",
        "que haces",
        "que puedo pedirte",
        "como funciona",
        "ver estos comandos",
        "ver comandos",
        "comandos",
        "muestrame los comandos",
        "mostrar comandos",
        "menu",
        "/help",
        "/ayuda",
        "que puedo hacer",
    }


def automation_configured() -> bool:
    return bool(os.getenv("AGENT_APP_ID") and os.getenv("AGENT_APP_PRIVATE_KEY"))


def help_text() -> str:
    if not automation_configured():
        return HELP
    return (
        "¡Hola! Soy AgentOps Tareas 🤖. Puedo preparar cambios de la aplicación, "
        "pedir aclaraciones, ejecutar pruebas y abrir un PR cuando el cambio apruebe.\n\n"
        "Escribe una petición concreta, usa ayuda o consulta estado <id>.\n"
        "La integración y el despliegue automáticos todavía están pendientes.\n"
        "No envíes secretos ni datos personales. Aplicación: " + APP_URL
    )


def queue_receipt(conn: psycopg.Connection, message: IncomingMessage) -> None:
    normalized = message.body.strip().casefold()
    if is_help(message.body):
        reply = help_text()
    elif normalized == "estado":
        reply = "Para consultar una solicitud escribe: estado <id>. Usa el id que te envié al registrarla."
    elif normalized.startswith("estado "):
        try:
            job_id = UUID(normalized.split(maxsplit=1)[1].strip())
        except ValueError:
            reply = "El id no tiene un formato válido. Copia el id completo de la solicitud."
        else:
            # Un remitente autorizado tampoco puede consultar solicitudes de otro.
            row = conn.execute(
                """SELECT j.state, j.summary FROM agentops_jobs j
                   JOIN agentops_inbox i ON i.message_id = j.message_id
                   WHERE j.id = %s AND i.sender = %s""",
                (job_id, message.sender),
            ).fetchone()
            if row:
                reply = f"Solicitud {job_id}\nEstado: {row[0]}."
                if row[0] == "received":
                    reply += "\nRecibida y guardada. " + (
                        "Pendiente de iniciar el agente."
                        if automation_configured()
                        else "El agente de corrección todavía no está conectado."
                    )
                elif row[1]:
                    reply += "\n" + row[1][:2400]
            else:
                reply = "No encontré esa solicitud entre las asociadas a tu número."
    else:
        waiting = conn.execute(
            """SELECT j.id, COALESCE(j.request_text,i.body),j.summary
            FROM agentops_jobs j JOIN agentops_inbox i ON i.message_id=j.message_id
            WHERE i.sender=%s AND j.state='needs_input' ORDER BY j.updated_at DESC
            LIMIT 1 FOR UPDATE OF j""",
            (message.sender,),
        ).fetchone()
        if waiting:
            job_id = waiting[0]
            conn.execute(
                """UPDATE agentops_jobs SET request_text=%s, state='received',
                dispatch_attempts=0,worker_run_id=NULL,lease=NULL,next_dispatch_at=now(),
                updated_at=now() WHERE id=%s""",
                (
                    waiting[1]
                    + "\nPregunta del agente: "
                    + waiting[2]
                    + "\nAclaracion: "
                    + message.body,
                    job_id,
                ),
            )
        else:
            job_id = uuid4()
            conn.execute(
                "INSERT INTO agentops_jobs (id, message_id) VALUES (%s, %s)",
                (job_id, message.message_id),
            )
        reply = (
            f"Recibí tu petición ✅\nId: {job_id}\nEstado: received (recibida y guardada).\n\n"
            "El agente de corrección todavía está en conexión. No he cambiado código ni desplegado.\n"
            f"Puedes consultar: estado {job_id}\nAplicación: {APP_URL}"
        )
        if automation_configured():
            reply = (
                f"Petición recibida ✅\nId: {job_id}\nIntentaré iniciar el agente en GitHub. "
                "Si falta información, te preguntaré por aquí.\n"
                f"Consulta: estado {job_id}\nAún no se confirma ningún cambio ni despliegue."
            )
    conn.execute(
        """INSERT INTO agentops_outbox (id, message_id, body, expires_at, event_key)
           VALUES (%s, %s, %s, %s, %s)""",
        (
            uuid4(),
            message.message_id,
            reply,
            message.sent_at + timedelta(hours=23),
            "receipt:" + message.message_id,
        ),
    )


@dataclass(frozen=True)
class PendingReply:
    id: UUID
    message_id: str
    phone_number_id: str
    sender: str
    body: str
    attempts: int


class ReplyStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def claim(self) -> PendingReply | None:
        with self.database.connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
            # Una caida despues de enviar podria haber sido aceptada por Meta.
            # No reenviar automaticamente un envio cuyo resultado se desconoce.
            cursor.execute("""UPDATE agentops_outbox SET state = 'uncertain',
                last_error = 'INTERRUPTED_SEND', updated_at = now()
                WHERE state = 'sending' AND claimed_at < now() - interval '2 minutes'""")
            cursor.execute("""UPDATE agentops_outbox SET state = 'expired', updated_at = now()
                WHERE state = 'pending' AND expires_at <= now()""")
            row = cursor.execute("""SELECT o.id, o.message_id, i.phone_number_id, i.sender,
                    o.body, o.attempts FROM agentops_outbox o
                JOIN agentops_inbox i ON i.message_id = o.message_id
                WHERE o.state = 'pending' AND o.next_attempt_at <= now()
                  AND o.expires_at > now() AND o.attempts < 3
                ORDER BY o.created_at FOR UPDATE OF o SKIP LOCKED LIMIT 1""").fetchone()
            if row is None:
                return None
            cursor.execute(
                """UPDATE agentops_outbox SET state = 'sending',
                attempts = attempts + 1, claimed_at = now(), updated_at = now()
                WHERE id = %s""",
                (row["id"],),
            )
            row["attempts"] += 1
        return PendingReply(**row)

    def sent(self, reply: PendingReply, provider_id: str) -> None:
        with self.database.connect() as conn:
            conn.execute(
                """UPDATE agentops_outbox SET state = 'sent', provider_message_id = %s,
                last_error = NULL, updated_at = now() WHERE id = %s AND state = 'sending'""",
                (provider_id, reply.id),
            )
            conn.execute(
                """UPDATE agentops_outbox SET delivery_status = s.status,
                    delivery_at = s.occurred_at
                FROM (SELECT status, occurred_at FROM agentops_delivery_status
                    WHERE message_id = %s ORDER BY occurred_at DESC LIMIT 1) s
                WHERE id = %s""",
                (provider_id, reply.id),
            )

    def failed(self, reply: PendingReply, reason: str, retryable: bool, uncertain: bool) -> None:
        state = (
            "uncertain"
            if uncertain
            else "pending"
            if retryable and reply.attempts < 3
            else "failed"
        )
        with self.database.connect() as conn:
            conn.execute(
                """UPDATE agentops_outbox SET state = %s, last_error = %s,
                next_attempt_at = now() + interval '60 seconds' * attempts, updated_at = now()
                WHERE id = %s AND state = 'sending'""",
                (state, reason, reply.id),
            )
