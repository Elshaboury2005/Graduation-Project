"""
app/messaging/exceptions.py
----------------------------
Exceptions raised by the Kafka messaging subsystem.

Each custom exception wraps lower-level errors (such as confluent_kafka's
KafkaException or underlying socket/connection errors) and provides clean,
actionable messages for application logs and API error responses.
"""

from __future__ import annotations


class KafkaMessagingError(Exception):
    """Base exception for all Kafka messaging errors."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause


class KafkaConnectionError(KafkaMessagingError):
    """
    Raised when the client cannot establish or maintain a connection to the
    Kafka broker.
    """


class KafkaTopicError(KafkaMessagingError):
    """
    Raised when an error occurs during topic creation, deletion, or metadata
    inspection.
    """


class KafkaProduceError(KafkaMessagingError):
    """
    Raised when producing a message or batch of messages fails or exceeds queue
    capacity.
    """


class KafkaConsumeError(KafkaMessagingError):
    """
    Raised when an unrecoverable error occurs while polling or consuming from
    Kafka.
    """
