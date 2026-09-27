"""
test_pubsub_and_cluster_graph.py
Unit & Integration tests for ClusterGraphStore and EventBus pub/sub capabilities.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from pipeline.cluster_graph import ClusterGraphStore
from shared.schemas import TransactionEvent
from api.pubsub import EventBus


def test_cluster_graph_store_ingestion_and_chain():
    store = ClusterGraphStore(fan_window_seconds=3600)
    
    # Ingest 3 hops: ACC_A -> ACC_B -> ACC_C -> ACC_ATM_99
    t0 = datetime.now(timezone.utc) - timedelta(minutes=10)
    t1 = t0 + timedelta(minutes=2)
    t2 = t1 + timedelta(minutes=2)
    
    e1 = TransactionEvent(
        transaction_id="TX_101",
        source_account_id="ACC_A",
        target_account_id="ACC_B",
        amount_inr=50000.0,
        timestamp=t0,
        payment_channel="IMPS",
        device_fingerprint="DEV_001",
    )
    e2 = TransactionEvent(
        transaction_id="TX_102",
        source_account_id="ACC_B",
        target_account_id="ACC_C",
        amount_inr=49000.0,
        timestamp=t1,
        payment_channel="NEFT",
        device_fingerprint="DEV_002",
    )
    e3 = TransactionEvent(
        transaction_id="TX_103",
        source_account_id="ACC_C",
        target_account_id="ACC_ATM_99",
        amount_inr=48000.0,
        timestamp=t2,
        payment_channel="UPI",
        device_fingerprint="DEV_003",
    )
    
    assert store.add_transaction(e1) is True
    # Test deduplication / idempotent ingestion
    assert store.add_transaction(e1) is False
    
    # Test batch sync
    assert store.sync_batch([e2, e3]) == 2
    
    # Verify backward causal chain from ACC_ATM_99
    chain = store.trace_global_multi_hop_chain("ACC_ATM_99", max_hops=5)
    assert len(chain) == 3
    assert chain[0].transaction_id == "TX_101"
    assert chain[1].transaction_id == "TX_102"
    assert chain[2].transaction_id == "TX_103"
    
    # Verify nodes exist in the graph
    assert store.graph.has_node("ACC_A")
    assert store.graph.has_node("ACC_B")
    assert store.graph.has_node("ACC_C")
    assert store.graph.has_node("ACC_ATM_99")


def test_event_bus_pubsub_fallback():
    async def _runner():
        bus = EventBus(redis_url=None)  # Forces in-memory queue fallback
        await bus.start()
        
        received_messages = []
        
        async def handler(payload: dict):
            received_messages.append(payload)
            
        bus.subscribe(handler)
        
        test_event = {"case_id": "NCRP-TEST-001", "action": "FREEZE_INITIATED", "amount": 100000}
        await bus.publish(test_event)
        
        # Allow background event dispatch
        await asyncio.sleep(0.05)
        
        assert len(received_messages) == 1
        assert received_messages[0]["case_id"] == "NCRP-TEST-001"
        assert received_messages[0]["action"] == "FREEZE_INITIATED"
        
        await bus.stop()

    asyncio.run(_runner())
