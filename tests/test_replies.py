import asyncio
import io
import json
import logging
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest

from bootstrap import outbound
from bootstrap.database import DeliveryStatus, IncomingMessage
from bootstrap.outbound import OutboundSettings, SendError, dispatch_one, send_text
from bootstrap.outbox import HELP, PendingReply, ReplyStore


def incoming(text="hola", sender="51900000001", age=0):
    return IncomingMessage(
        "wamid." + uuid4().hex,
        "12345",
        sender,
        text,
        datetime.now(UTC) - timedelta(hours=age),
    )


def counts(database):
    with database.connect() as conn:
        return tuple(
            conn.execute(
                "SELECT (SELECT count(*) FROM agentops_inbox), (SELECT count(*) FROM agentops_outbox), (SELECT count(*) FROM agentops_jobs)"
            ).fetchone()
        )


def test_duplicate_message_queues_exactly_one_reply(database):
    message = incoming()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: database.save([message], []), range(8)))
    assert counts(database) == (1, 1, 0)
    reply = ReplyStore(database).claim()
    assert reply.body == HELP
    assert ReplyStore(database).claim() is None


def test_request_and_status_are_private_to_sender(database):
    first = incoming("Agrega un filtro ficticio")
    database.save([first], [])
    assert counts(database) == (1, 1, 1)
    with database.connect() as conn:
        job_id = conn.execute("SELECT id FROM agentops_jobs").fetchone()[0]
    owner = incoming("estado " + str(job_id))
    other = incoming("estado " + str(job_id), sender="51900000002")
    database.save([owner, other], [])
    with database.connect() as conn:
        replies = dict(conn.execute("SELECT message_id, body FROM agentops_outbox").fetchall())
    assert "Estado: received" in replies[owner.message_id]
    assert "No encontré" in replies[other.message_id]
    assert counts(database) == (3, 3, 1)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("estado", "estado <id>"),
        ("estado incorrecto", "formato válido"),
        ("estado " + str(uuid4()), "No encontré"),
        ("ayuda", "comandos"),
    ],
)
def test_support_commands_dont_create_jobs(database, text, expected):
    database.save([incoming(text)], [])
    reply = ReplyStore(database).claim()
    assert expected in reply.body
    assert counts(database) == (1, 1, 0)


def test_batch_failure_rolls_back_replies_and_jobs(database):
    with pytest.raises(psycopg.IntegrityError):
        database.save(
            [incoming("Una solicitud ficticia")], [DeliveryStatus("bad", None, datetime.now(UTC))]
        )
    assert counts(database) == (0, 0, 0)


def test_multiple_workers_claim_different_replies(database):
    database.save([incoming(str(number)) for number in range(8)], [])
    store = ReplyStore(database)
    with ThreadPoolExecutor(max_workers=4) as pool:
        replies = list(pool.map(lambda _: store.claim(), range(10)))
    assert len({reply.id for reply in replies if reply}) == 8
    assert sum(reply is None for reply in replies) == 2


def test_expired_messages_not_sent(database):
    database.save([incoming(age=24)], [])
    assert ReplyStore(database).claim() is None
    with database.connect() as conn:
        assert conn.execute("SELECT state, attempts FROM agentops_outbox").fetchone() == (
            "expired",
            0,
        )


def test_interrupted_and_uncertain_sends_are_not_automatically_repeated(database):
    database.save([incoming()], [])
    store = ReplyStore(database)
    reply = store.claim()
    with database.connect() as conn:
        conn.execute("UPDATE agentops_outbox SET claimed_at = now() - interval '3 minutes'")
    assert store.claim() is None
    with database.connect() as conn:
        assert conn.execute(
            "SELECT state, last_error FROM agentops_outbox WHERE id = %s", (reply.id,)
        ).fetchone() == ("uncertain", "INTERRUPTED_SEND")


def test_rate_limit_has_three_bounded_attempts(database):
    database.save([incoming()], [])
    store = ReplyStore(database)
    for number in range(1, 4):
        reply = store.claim()
        assert reply.attempts == number
        store.failed(reply, "WHATSAPP_RATE_LIMIT", True, False)
        with database.connect() as conn:
            state = conn.execute("SELECT state FROM agentops_outbox").fetchone()[0]
            assert state == ("pending" if number < 3 else "failed")
            conn.execute("UPDATE agentops_outbox SET next_attempt_at = now()")
    assert store.claim() is None


def test_delivery_status_before_and_after_acceptance(database):
    database.save([incoming()], [])
    store = ReplyStore(database)
    reply = store.claim()
    delivered = DeliveryStatus("wamid.outbound-test", "delivered", datetime.now(UTC))
    database.save([], [delivered])
    store.sent(reply, delivered.message_id)
    read = DeliveryStatus(
        delivered.message_id, "read", delivered.occurred_at + timedelta(seconds=1)
    )
    database.save([], [read, delivered])
    with database.connect() as conn:
        assert conn.execute("SELECT state, delivery_status FROM agentops_outbox").fetchone() == (
            "sent",
            "read",
        )
    assert store.claim() is None


def settings():
    return OutboundSettings(
        token="private-test-token",
        phone_number_id="12345",
        allowed_senders=frozenset({"51900000001"}),
    )


def pending():
    return PendingReply(uuid4(), "wamid.original", "12345", "51900000001", "Respuesta ficticia", 1)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def fake_transport(monkeypatch, response=None, exception=None, inspect=None):
    class Opener:
        def open(self, request, timeout):
            assert timeout == 10
            if inspect:
                inspect(request)
            if exception:
                raise exception
            return FakeResponse(response)

    monkeypatch.setattr(outbound.urllib.request, "build_opener", lambda *_: Opener())


def test_text_uses_fixed_graph_endpoint_and_bearer_header(monkeypatch):
    def inspect(request):
        assert request.full_url == "https://graph.facebook.com/v26.0/12345/messages"
        assert request.get_header("Authorization") == "Bearer private-test-token"
        body = json.loads(request.data)
        assert "private-test-token" not in request.data.decode()
        assert body["to"] == "51900000001"
        assert body["context"]["message_id"] == "wamid.original"
        assert body["text"] == {"preview_url": False, "body": "Respuesta ficticia"}

    fake_transport(monkeypatch, b'{"messages":[{"id":"wamid.sent-test"}]}', inspect=inspect)
    assert send_text(settings(), pending()) == "wamid.sent-test"
    assert "private-test-token" not in repr(settings())
    assert (
        outbound.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")
        is None
    )


@pytest.mark.parametrize(
    "status, code, reason, retryable, uncertain",
    [
        (401, 190, "WHATSAPP_TOKEN_INVALID_OR_EXPIRED", False, False),
        (400, 131047, "REPLY_WINDOW_CLOSED", False, False),
        (429, 4, "WHATSAPP_RATE_LIMIT", True, False),
        (400, 131056, "WHATSAPP_RATE_LIMIT", True, False),
        (403, 10, "WHATSAPP_HTTP_ERROR_403", False, False),
        (500, 1, "WHATSAPP_HTTP_ERROR_500", False, True),
    ],
)
def test_safe_meta_errors(monkeypatch, status, code, reason, retryable, uncertain):
    raw = json.dumps({"error": {"code": code, "message": "sensitive-private-data"}}).encode()
    error = urllib.error.HTTPError(
        "https://graph.facebook.com", status, "private", {}, io.BytesIO(raw)
    )
    fake_transport(monkeypatch, exception=error)
    with pytest.raises(SendError) as failure:
        send_text(settings(), pending())
    assert failure.value.reason == reason
    assert failure.value.retryable == retryable and failure.value.uncertain == uncertain
    assert "sensitive-private-data" not in str(failure.value)


@pytest.mark.parametrize(
    "response",
    [b"{}", b"bad-json", b'{"messages":[]}', b'{"messages":[{"id":123}]}', b"x" * 65537],
    ids=["empty", "not_json", "empty_messages", "invalid_id", "oversized"],
)
def test_bad_success_response_is_uncertain_not_retryable(monkeypatch, response):
    fake_transport(monkeypatch, response)
    with pytest.raises(SendError) as failure:
        send_text(settings(), pending())
    assert failure.value.uncertain and not failure.value.retryable


def test_timeout_is_uncertain_and_unauthorized_destination_never_sent(monkeypatch):
    fake_transport(monkeypatch, exception=TimeoutError())
    with pytest.raises(SendError, match="WHATSAPP_NETWORK_ERROR") as failure:
        send_text(settings(), pending())
    assert failure.value.uncertain
    restricted = settings().model_copy(update={"allowed_senders": frozenset({"51900000002"})})
    with pytest.raises(SendError, match="RECIPIENT_NOT_ALLOWED"):
        send_text(restricted, pending())


def test_dispatch_acceptance_and_failure_are_durable(database, monkeypatch, caplog):
    database.save([incoming()], [])
    store = ReplyStore(database)
    caplog.set_level(logging.INFO, logger="uvicorn.error.agentops")
    monkeypatch.setattr(outbound, "send_text", lambda *_: "wamid.sent-test")
    assert dispatch_one(store, settings())
    assert not dispatch_one(store, settings())
    assert "accepted_by_meta" in caplog.text and "51900000001" not in caplog.text
    database.save([incoming()], [])

    def fail(*_):
        raise SendError("WHATSAPP_TOKEN_INVALID_OR_EXPIRED")

    monkeypatch.setattr(outbound, "send_text", fail)
    assert dispatch_one(store, settings())
    with database.connect() as conn:
        assert (
            conn.execute("SELECT count(*) FROM agentops_outbox WHERE state='failed'").fetchone()[0]
            == 1
        )
    assert "private-test-token" not in caplog.text


def test_worker_missing_key_is_inactive_and_stops_when_requested(
    database, monkeypatch, receiver_env
):
    async def not_configured():
        await outbound.reply_worker(database, asyncio.Event())

    asyncio.run(not_configured())
    monkeypatch.setenv("WHATSAPP_TOKEN", "private-test-token")

    async def configured():
        stop = asyncio.Event()

        def dispatch(*_):
            stop.set()
            return False

        monkeypatch.setattr(outbound, "dispatch_one", dispatch)
        await outbound.reply_worker(database, stop)

    asyncio.run(configured())
