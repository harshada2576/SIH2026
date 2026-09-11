"""
shared/kafka_utils.py

Shared Kafka utilities, canonical topic names, consumer group names,
and standard producer/consumer factory helpers for SIH2026.
"""

import json
import logging
import os
import socket
from typing import Any, Callable
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

log = logging.getLogger("kafka_utils")

# Canonical Bootstrap Servers (can be overridden via environment variable)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))

# Canonical Topic Names matching Architecture.md §7
TRANSACTIONS_TOPIC = "transactions"
GRAPH_SIGNALS_TOPIC = "graph_signals"
RISK_ALERTS_TOPIC = "risk_alerts"

# Canonical Consumer Groups
GRAPH_BUILDER_GROUP = "graph-builder-group"
SCORER_GROUP = "scorer-group"


def safe_json_serializer(data: Any) -> bytes:
    """Serializes a Python dict/object to UTF-8 encoded JSON bytes."""
    return json.dumps(data).encode("utf-8")


def safe_key_serializer(key: Any) -> bytes | None:
    """Serializes string partition keys to UTF-8 bytes."""
    if key is None:
        return None
    if isinstance(key, str):
        return key.encode("utf-8")
    return bytes(key)


def safe_json_deserializer(raw_bytes: bytes | str | None) -> dict | None:
    """
    Safely deserializes UTF-8 JSON bytes into a Python dict.
    Returns None if the payload is corrupted or malformed (poison pill)
    rather than raising an unhandled exception.
    """
    if raw_bytes is None:
        return None
    try:
        if isinstance(raw_bytes, str):
            return json.loads(raw_bytes)
        return json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
        log.warning(f"Poison-pill payload rejected during deserialization: {e}")
        return None


def is_kafka_available(bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS, timeout_sec: float = 2.0) -> bool:
    """
    Quick non-blocking probe to verify whether the Kafka broker socket is reachable.
    Useful for test environments and pre-flight health checks.
    """
    try:
        host, port_str = bootstrap_servers.split(":", 1)
        port = int(port_str)
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def get_kafka_producer(
    bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
    client_id: str | None = None,
    value_serializer: Callable[[Any], bytes] = safe_json_serializer,
    key_serializer: Callable[[Any], bytes | None] = safe_key_serializer,
    **kwargs: Any,
) -> KafkaProducer:
    """
    Creates and returns a standardized KafkaProducer instance with
    idempotent delivery defaults and explicit serialization.
    """
    if not is_kafka_available(bootstrap_servers, timeout_sec=0.5):
        raise ConnectionError(
            f"Kafka broker not reachable at '{bootstrap_servers}'. "
            f"For standalone hackathon demo, run: python -m scripts.run_hackathon"
        )

    config: dict[str, Any] = {
        "bootstrap_servers": bootstrap_servers,
        "value_serializer": value_serializer,
        "key_serializer": key_serializer,
        "acks": "all",
        "retries": 3,
    }
    if client_id:
        config["client_id"] = client_id
    config.update(kwargs)
    return KafkaProducer(**config)


def get_kafka_consumer(
    *topics: str,
    bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
    group_id: str | None = None,
    auto_offset_reset: str = "earliest",
    enable_auto_commit: bool = True,
    consumer_timeout_ms: int = 1000,
    value_deserializer: Callable[[bytes], Any] = safe_json_deserializer,
    client_id: str | None = None,
    **kwargs: Any,
) -> KafkaConsumer:
    """
    Creates and returns a standardized KafkaConsumer instance subscribed to the given topics.
    """
    if not is_kafka_available(bootstrap_servers, timeout_sec=0.5):
        raise ConnectionError(
            f"Kafka broker not reachable at '{bootstrap_servers}'. "
            f"For standalone hackathon demo, run: python -m scripts.run_hackathon"
        )
    config: dict[str, Any] = {
        "bootstrap_servers": bootstrap_servers,
        "auto_offset_reset": auto_offset_reset,
        "enable_auto_commit": enable_auto_commit,
        "consumer_timeout_ms": consumer_timeout_ms,
        "value_deserializer": value_deserializer,
    }
    if group_id:
        config["group_id"] = group_id
    if client_id:
        config["client_id"] = client_id
    config.update(kwargs)
    return KafkaConsumer(*topics, **config)
