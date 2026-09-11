"""
pipeline/partition_strategy.py

Defines how transaction events get assigned to Kafka partitions.

IMPORTANT: this function must be used by BOTH the producer (data-generator team)
and understood by the consumer (this workstream) — they don't need to call it
identically, but the producer MUST use this as its Kafka message key so Kafka's
default hashing partitioner keeps one account's transactions together and
ordered. Flag any change here to the group per Rules.md.

Why source_account_id and not district/region: the locked transaction schema
deliberately excludes location fields (those live in Terminals, looked up
separately). Partitioning by source_account_id is the standard Kafka pattern
for keeping a single entity's event order intact, and it doubles as a natural
sharding key for scaling consumers horizontally.
"""

import hashlib


def get_partition_key(transaction: dict) -> str:
    """
    Returns the Kafka message key to use when producing this transaction.
    Kafka's default partitioner hashes this key to pick a partition, so the
    same source_account_id always lands on the same partition.
    """
    return transaction["source_account_id"]


def partition_for_key(key: str, num_partitions: int) -> int:
    """
    Optional: explicit partition calculation, useful for the load-test script
    or for demonstrating/explaining the scalability slide (e.g. "here's how
    N accounts distribute across P partitions").
    Not required if you let the Kafka client's built-in partitioner handle it
    from get_partition_key() alone — this is mainly for visibility/demo purposes.
    """
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest, 16) % num_partitions
