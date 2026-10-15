import threading
import time
from collections import OrderedDict
from typing import Optional, Dict
from agy_cursor_bridge.config import settings

class SessionEntry:
    def __init__(self, agy_conversation_id: str):
        self.agy_conversation_id = agy_conversation_id
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.turn_count = 1

    def touch(self):
        self.last_accessed = time.time()
        self.turn_count += 1

class SessionStore:
    def __init__(self, max_size: int = settings.max_cached_sessions, ttl: int = settings.session_ttl_seconds):
        self._max_size = max(1, max_size)
        self._ttl = max(1, ttl)
        self._store: OrderedDict[str, SessionEntry] = OrderedDict()
        self._lock = threading.RLock()

    def get_conversation_id(self, fingerprint: str) -> Optional[str]:
        if not fingerprint:
            return None

        with self._lock:
            if fingerprint not in self._store:
                return None

            entry = self._store[fingerprint]
            # Check TTL
            if time.time() - entry.last_accessed > self._ttl:
                del self._store[fingerprint]
                return None

            # Move to end (LRU)
            self._store.move_to_end(fingerprint)
            entry.touch()
            return entry.agy_conversation_id

    def set_conversation_id(self, fingerprint: str, agy_conversation_id: str):
        if not fingerprint or not agy_conversation_id:
            return

        with self._lock:
            if fingerprint in self._store:
                self._store[fingerprint].agy_conversation_id = agy_conversation_id
                self._store[fingerprint].touch()
                self._store.move_to_end(fingerprint)
            else:
                while len(self._store) >= self._max_size:
                    # Evict oldest item
                    self._store.popitem(last=False)
                self._store[fingerprint] = SessionEntry(agy_conversation_id)

    def prune_expired(self) -> int:
        now = time.time()
        with self._lock:
            expired_keys = [
                k for k, v in self._store.items()
                if now - v.last_accessed > self._ttl
            ]
            for k in expired_keys:
                del self._store[k]
            return len(expired_keys)

    def clear(self):
        with self._lock:
            self._store.clear()

    @property
    def active_sessions_count(self) -> int:
        with self._lock:
            return len(self._store)

# Global singleton
session_store = SessionStore()
