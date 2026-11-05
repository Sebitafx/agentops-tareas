"""PostgreSQL transaccional; sin conexiones ni credenciales al importar el modulo."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from bootstrap.outbox import queue_receipt

MIGRATIONS = Path(__file__).parent / "migrations"
SCHEMA_VERSION = "005_conversation.sql"


class SchemaError(Exception):
    """Una migracion aplicada cambio o la base no tiene el esquema esperado."""


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    phone_number_id: str
    sender: str
    body: str
    sent_at: datetime


@dataclass(frozen=True)
class DeliveryStatus:
    message_id: str
    status: str
    occurred_at: datetime


class Database:
    def __init__(self, url: str) -> None:
        self._url = url

    def connect(self) -> psycopg.Connection:
        # No imprimir errores del driver: pueden incluir host o credenciales.
        return psycopg.connect(self._url, connect_timeout=5, prepare_threshold=None)

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.execute("SET LOCAL statement_timeout = '15s'")
            conn.execute("SET LOCAL lock_timeout = '10s'")
            # Lock de transaccion compatible con el pooling de Neon.
            conn.execute("SELECT pg_advisory_xact_lock(19771103)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agentops_schema_versions (
                    version TEXT PRIMARY KEY,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            for path in sorted(MIGRATIONS.glob("*.sql")):
                script = path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(script.encode()).hexdigest()
                row = conn.execute(
                    "SELECT checksum FROM agentops_schema_versions WHERE version = %s",
                    (path.name,),
                ).fetchone()
                if row:
                    if row[0] != checksum:
                        raise SchemaError("Migracion aplicada modificada")
                    continue
                conn.execute(script, prepare=False)
                conn.execute(
                    "INSERT INTO agentops_schema_versions (version, checksum) VALUES (%s, %s)",
                    (path.name, checksum),
                )

    def check(self) -> None:
        with self.connect() as conn:
            conn.execute("SET LOCAL statement_timeout = '3s'")
            row = conn.execute(
                "SELECT version FROM agentops_schema_versions WHERE version = %s",
                (SCHEMA_VERSION,),
            ).fetchone()
            if not row:
                raise SchemaError("Migracion pendiente")
            conn.execute("SELECT 1 FROM agentops_inbox LIMIT 0")
            conn.execute("SELECT 1 FROM agentops_delivery_status LIMIT 0")
            conn.execute("SELECT 1 FROM agentops_tasks LIMIT 0")
            conn.execute("SELECT 1 FROM agentops_jobs LIMIT 0")
            conn.execute("SELECT 1 FROM agentops_outbox LIMIT 0")

    def save(self, messages: list[IncomingMessage], statuses: list[DeliveryStatus]) -> None:
        # El contexto confirma TODO el lote antes de responder 200 a Meta.
        # Si cualquier sentencia falla, se revierte TODO para permitir el reintento.
        with self.connect() as conn:
            conn.execute("SET LOCAL statement_timeout = '5s'")
            conn.execute("SET LOCAL lock_timeout = '3s'")
            for message in messages:
                inserted = conn.execute(
                    """INSERT INTO agentops_inbox
                       (message_id, phone_number_id, sender, body, sent_at)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (message_id) DO NOTHING RETURNING message_id""",
                    (
                        message.message_id,
                        message.phone_number_id,
                        message.sender,
                        message.body,
                        message.sent_at,
                    ),
                ).fetchone()
                if inserted:
                    queue_receipt(conn, message)
            for status in statuses:
                conn.execute(
                    """INSERT INTO agentops_delivery_status (message_id, status, occurred_at)
                       VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                    (status.message_id, status.status, status.occurred_at),
                )
                conn.execute(
                    """UPDATE agentops_outbox SET delivery_status = %s, delivery_at = %s,
                        updated_at = now() WHERE provider_message_id = %s
                        AND (delivery_at IS NULL OR delivery_at <= %s)""",
                    (status.status, status.occurred_at, status.message_id, status.occurred_at),
                )

    def summary(self) -> dict[str, int]:
        """Uso administrativo desde consola; nunca publicar telefonos ni textos."""
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT count(*) AS messages FROM agentops_inbox")
            return dict(cursor.fetchone() or {})
