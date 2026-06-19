"""
Novel-Claude Fusion — Prompt Cache

Hash-based exact match cache to avoid redundant LLM calls.
Lightweight: in-memory with optional disk persistence.
Pattern: 2026 industry standard (hash key = model + system + user prompt).

Usage:
  from utils.prompt_cache import PromptCache
  cache = PromptCache()
  result = cache.get_or_call(prompt, system, model, call_fn)
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = Path(os.path.expanduser("~/.novel_claude_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class PromptCache:
    """Simple hash-based prompt cache. TTL-based eviction, optional disk persistence."""

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 500,
                 persist: bool = True):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self.persist = persist
        self._cache: Dict[str, Tuple[float, str]] = {}
        self._hits = 0
        self._misses = 0
        if persist:
            self._load()

    def _hash(self, model: str, system: str, prompt: str) -> str:
        content = f"{model}|{system[:200]}|{prompt[:500]}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(self, model: str, system: str, prompt: str) -> Optional[str]:
        """Get cached result, or None if not found/expired."""
        key = self._hash(model, system, prompt)
        if key not in self._cache:
            self._misses += 1
            return None
        timestamp, result = self._cache[key]
        if time.time() - timestamp > self.ttl:
            del self._cache[key]
            self._misses += 1
            return None
        self._hits += 1
        return result

    def set(self, model: str, system: str, prompt: str, result: str):
        """Store a result in cache."""
        key = self._hash(model, system, prompt)
        self._cache[key] = (time.time(), result)
        # Evict oldest if over max
        if len(self._cache) > self.max_entries:
            oldest = min(self._cache.items(), key=lambda x: x[1][0])
            del self._cache[oldest[0]]

    def get_or_call(self, model: str, system: str, prompt: str,
                    call_fn: Callable[[], str]) -> str:
        """Get cached result or call function and cache."""
        cached = self.get(model, system, prompt)
        if cached is not None:
            return cached
        result = call_fn()
        if result:
            self.set(model, system, prompt, result)
            if self.persist and self._misses % 10 == 0:
                self._save()
        return result

    def stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = self._hits / max(total, 1)
        return {
            "entries": len(self._cache),
            "hits": self._hits, "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
            "ttl_seconds": self.ttl,
        }

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def _save(self):
        try:
            path = CACHE_DIR / "prompt_cache.json"
            data = {
                "entries": {k: [ts, res] for k, (ts, res) in self._cache.items()},
                "hits": self._hits, "misses": self._misses,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _load(self):
        try:
            path = CACHE_DIR / "prompt_cache.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache = {k: tuple(v) for k, v in data.get("entries", {}).items()}
                self._hits = data.get("hits", 0)
                self._misses = data.get("misses", 0)
        except Exception:
            pass


# Global singleton
_global_cache: Optional[PromptCache] = None


def get_cache() -> PromptCache:
    global _global_cache
    if _global_cache is None:
        _global_cache = PromptCache()
    return _global_cache
