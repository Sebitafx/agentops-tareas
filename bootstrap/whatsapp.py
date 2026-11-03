"""Validacion de mensajes de Meta: firma sobre bytes originales y lista permitida."""

import hashlib
import hmac
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from bootstrap.database import DeliveryStatus, IncomingMessage

MAX_BODY_BYTES = 262144


def valid_signature(body: bytes, signature: str, secret: str) -> bool:
    if not secret or not re.fullmatch(r"sha256=[0-9a-fA-F]{64}", signature):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower())


class Text(BaseModel):
    body: str = Field(min_length=1, max_length=16384)


class Message(BaseModel):
    id: str = Field(min_length=1, max_length=512)
    sender: str = Field(alias="from", pattern=r"^[0-9]{5,20}$")
    timestamp: int = Field(ge=0, le=4102444800)
    type: str
    text: Text | None = None


class Status(BaseModel):
    id: str = Field(min_length=1, max_length=512)
    status: str = Field(min_length=1, max_length=100)
    timestamp: int = Field(ge=0, le=4102444800)


class Metadata(BaseModel):
    phone_number_id: str


class Value(BaseModel):
    metadata: Metadata
    messages: list[Message] = Field(default_factory=list, max_length=100)
    statuses: list[Status] = Field(default_factory=list, max_length=100)


class Change(BaseModel):
    field: str
    value: dict


class Entry(BaseModel):
    changes: list[Change] = Field(max_length=100)


class Event(BaseModel):
    object: Literal["whatsapp_business_account"]
    entry: list[Entry] = Field(max_length=100)


class ReceiverSettings(BaseModel):
    secret: str = Field(min_length=1)
    phone_number_id: str = Field(pattern=r"^[0-9]+$")
    allowed_senders: frozenset[str] = Field(min_length=1)

    @field_validator("allowed_senders")
    @classmethod
    def digits_only(cls, senders: frozenset[str]) -> frozenset[str]:
        if any(not re.fullmatch(r"[0-9]{5,20}", sender) for sender in senders):
            raise ValueError("Usar numeros completos sin +, espacios ni guiones")
        return senders


def extract(
    event: Event, settings: ReceiverSettings
) -> tuple[list[IncomingMessage], list[DeliveryStatus]]:
    messages: list[IncomingMessage] = []
    statuses: list[DeliveryStatus] = []
    for entry in event.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue
            value = Value.model_validate(change.value)
            if value.metadata.phone_number_id != settings.phone_number_id:
                continue
            for message in value.messages:
                if message.sender not in settings.allowed_senders or message.type != "text":
                    continue
                if message.text is None:
                    raise ValueError("Mensaje de texto sin texto")
                messages.append(
                    IncomingMessage(
                        message.id,
                        value.metadata.phone_number_id,
                        message.sender,
                        message.text.body,
                        datetime.fromtimestamp(message.timestamp, UTC),
                    )
                )
            statuses.extend(
                DeliveryStatus(
                    status.id, status.status, datetime.fromtimestamp(status.timestamp, UTC)
                )
                for status in value.statuses
            )
    return messages, statuses
