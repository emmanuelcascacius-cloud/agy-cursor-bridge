import time
import concurrent.futures
import pytest
from agy_cursor_bridge.core.session_store import SessionStore

def test_session_store_basic():
    store = SessionStore(max_size=5, ttl=10)
    assert store.active_sessions_count == 0
    assert store.get_conversation_id("fp1") is None

    store.set_conversation_id("fp1", "conv-101")
    assert store.active_sessions_count == 1
    assert store.get_conversation_id("fp1") == "conv-101"

    # Update existing
    store.set_conversation_id("fp1", "conv-102")
    assert store.active_sessions_count == 1
    assert store.get_conversation_id("fp1") == "conv-102"

def test_session_store_lru_eviction():
    store = SessionStore(max_size=3, ttl=100)
    store.set_conversation_id("fp1", "c1")
    store.set_conversation_id("fp2", "c2")
    store.set_conversation_id("fp3", "c3")
    assert store.active_sessions_count == 3

    # Access fp1 so it becomes recently used: order is now [fp2, fp3, fp1]
    assert store.get_conversation_id("fp1") == "c1"

    # Add fp4 -> fp2 should be evicted as oldest
    store.set_conversation_id("fp4", "c4")
    assert store.active_sessions_count == 3
    assert store.get_conversation_id("fp2") is None
    assert store.get_conversation_id("fp1") == "c1"
    assert store.get_conversation_id("fp3") == "c3"
    assert store.get_conversation_id("fp4") == "c4"

def test_session_store_ttl_expiry():
    store = SessionStore(max_size=10, ttl=1)
    store.set_conversation_id("fp_fast", "c_fast")
    assert store.get_conversation_id("fp_fast") == "c_fast"

    # Artificially age the entry
    time.sleep(1.1)
    # Access should detect expired and return None
    assert store.get_conversation_id("fp_fast") is None
    assert store.active_sessions_count == 0

    # Test prune_expired
    store.set_conversation_id("fp_prune", "c_prune")
    time.sleep(1.1)
    pruned = store.prune_expired()
    assert pruned == 1
    assert store.active_sessions_count == 0

def test_session_store_concurrency():
    store = SessionStore(max_size=20, ttl=60)

    def worker(worker_id: int):
        for i in range(50):
            fp = f"fp_{worker_id}_{i % 5}"
            conv = f"conv_{worker_id}_{i}"
            store.set_conversation_id(fp, conv)
            val = store.get_conversation_id(fp)
            assert val is not None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, w) for w in range(10)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    assert store.active_sessions_count <= 20
