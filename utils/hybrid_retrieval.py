"""
Novel-Claude Fusion — Hybrid Retrieval Engine

Lightweight, zero-dependency retrieval for long-form fiction memory.
Replaces ChromaDB with BM25 + TF-IDF + optional llama.cpp embeddings.

Design: 2026 industry consensus — hybrid retrieval (BM25 keywords + semantic vectors)
beats pure vector search for fiction, where character names and specific terms
get diluted in dense embeddings.

Sources:
  - Towards AI: "Hybrid Search RAG That Actually Works" (Jan 2026)
  - novels-agent: BM25+vector hybrid for Chinese web novels (May 2026)
  - SQLite FTS5 + BM25 pattern (obsidian-tools, UBOS)

Architecture:
  BM25 (keyword precision) + TF-IDF bigrams (phrase matching)
  + optional llama.cpp embeddings (semantic breadth)
  -> RRF (Reciprocal Rank Fusion) -> ranked results
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

import requests


# ── tokenizer ─────────────────────────────────────────────────────────────────

def _tokenize(text: str, ngram: int = 1) -> List[str]:
    """Chinese-aware tokenizer: chars + bigrams for phrase matching."""
    # Clean
    text = re.sub(r'[，。！？、；：""''（）\n\r\t ]+', ' ', text)
    # Extract CJK chars as individual tokens + bigrams
    cjk = re.findall(r'[一-鿿]+', text)
    tokens = []
    for word in cjk:
        if len(word) == 1:
            tokens.append(word)
        else:
            # Unigrams
            if ngram >= 1:
                tokens.extend(list(word))
            # Bigrams for phrase matching
            if ngram >= 2:
                for i in range(len(word) - 1):
                    tokens.append(word[i:i + 2])
    # Non-CJK words
    non_cjk = re.findall(r'[a-zA-Z0-9]+', text)
    tokens.extend(w.lower() for w in non_cjk)
    return tokens


# ── BM25 ─────────────────────────────────────────────────────────────────────

class BM25Index:
    """
    BM25 keyword index with TF-IDF scoring.
    Zero external dependencies, pure Python.

    k1: term frequency saturation (default 1.5)
    b: document length normalization (default 0.75)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[str] = []
        self.doc_metadata: List[dict] = []
        self._tokenized: List[List[str]] = []
        self._df: Counter = Counter()      # document frequency
        self._avgdl: float = 0.0            # average document length

    def add(self, text: str, metadata: dict = None) -> int:
        """Add a document, return its index."""
        tokens = _tokenize(text, ngram=2)
        idx = len(self.documents)
        self.documents.append(text)
        self.doc_metadata.append(metadata or {})
        self._tokenized.append(tokens)

        # Update DF
        self._df.update(set(tokens))

        # Update average length
        total_len = sum(len(t) for t in self._tokenized)
        self._avgdl = total_len / len(self._tokenized) if self._tokenized else 0

        return idx

    def add_batch(self, items: List[Tuple[str, dict]]) -> None:
        """Add multiple documents at once."""
        for text, meta in items:
            self.add(text, meta)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float, str, dict]]:
        """
        Search and return [(doc_index, score, text, metadata), ...] sorted by score desc.
        """
        if not self.documents:
            return []

        query_tokens = _tokenize(query, ngram=2)
        if not query_tokens:
            return []

        scores = []
        N = len(self._tokenized)

        for i, doc_tokens in enumerate(self._tokenized):
            score = 0.0
            doc_len = len(doc_tokens)
            tf = Counter(doc_tokens)

            for token in set(query_tokens):
                if token not in tf:
                    continue
                # BM25 formula
                df = self._df.get(token, 0)
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                tf_td = tf[token]
                numerator = tf_td * (self.k1 + 1)
                denominator = tf_td + self.k1 * (1 - self.b + self.b * doc_len / self._avgdl)
                score += idf * numerator / denominator

            if score > 0:
                scores.append((i, score, self.documents[i], self.doc_metadata[i]))

        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]

    def __len__(self) -> int:
        return len(self.documents)


# ── TF-IDF bigram ────────────────────────────────────────────────────────────

class TFIDFIndex:
    """TF-IDF with bigram support for phrase-level matching."""

    def __init__(self):
        self.documents: List[str] = []
        self.doc_metadata: List[dict] = []
        self._tokenized: List[List[str]] = []
        self._idf: Dict[str, float] = {}

    def add(self, text: str, metadata: dict = None) -> int:
        idx = len(self.documents)
        self.documents.append(text)
        self.doc_metadata.append(metadata or {})
        self._tokenized.append(_tokenize(text, ngram=2))
        return idx

    def add_batch(self, items: List[Tuple[str, dict]]) -> None:
        for text, meta in items:
            self.add(text, meta)

    def _build_idf(self):
        N = len(self._tokenized)
        df = Counter()
        for tokens in self._tokenized:
            df.update(set(tokens))
        self._idf = {word: math.log((N + 1) / (count + 1)) + 1.0
                     for word, count in df.items()}

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float, str, dict]]:
        if not self.documents:
            return []
        if not self._idf:
            self._build_idf()

        query_tokens = _tokenize(query, ngram=2)
        scores = []
        for i, doc_tokens in enumerate(self._tokenized):
            tf = Counter(doc_tokens)
            vec = [tf.get(t, 0) * self._idf.get(t, 0) for t in query_tokens]
            q_vec = [1.0] * len(query_tokens)  # uniform query weight
            dot = sum(a * b for a, b in zip(vec, q_vec))
            norm1 = math.sqrt(sum(a * a for a in vec))
            norm2 = math.sqrt(len(query_tokens))
            if norm1 > 0 and norm2 > 0:
                score = dot / (norm1 * norm2)
                if score > 0:
                    scores.append((i, score, self.documents[i], self.doc_metadata[i]))

        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]


# ── Optional embedding client (llama.cpp) ────────────────────────────────────

class EmbeddingClient:
    """
    Lightweight embedding client for llama.cpp's built-in /v1/embeddings endpoint.
    Uses the existing llama-router on localhost:61183.
    BGE-M3, m3e-small, or jina-v5-nano can be added as embedding models.

    Falls back gracefully to None if embedding server unavailable.
    """

    def __init__(self, base_url: str = "http://localhost:61183/v1",
                 model: str = None, timeout: int = 10):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self._available: Optional[bool] = None

    def available(self) -> bool:
        """Check if embedding endpoint is reachable."""
        if self._available is not None:
            return self._available
        try:
            r = requests.get(f"{self.base_url}/models", timeout=3)
            self._available = r.status_code == 200
        except Exception:
            self._available = False
        return self._available

    def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Get embeddings for texts. Returns None if unavailable."""
        if not self.available():
            return None
        try:
            # Truncate long texts
            truncated = [t[:8000] for t in texts]
            payload = {"input": truncated}
            if self.model:
                payload["model"] = self.model

            r = requests.post(
                f"{self.base_url}/embeddings",
                json=payload,
                timeout=self.timeout,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            return [item["embedding"] for item in data.get("data", [])]
        except Exception:
            return None


# ── Hybrid retriever ─────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    """Single retrieval result."""
    text: str
    score: float
    metadata: dict = field(default_factory=dict)
    source: str = "bm25"  # "bm25", "tfidf", "embedding", "hybrid"


class HybridRetriever:
    """
    Hybrid retrieval combining BM25 + TF-IDF + optional embeddings.

    Uses Reciprocal Rank Fusion (RRF) to merge results from multiple backends.
    Falls back gracefully: if embeddings unavailable, uses BM25+TFIDF only.
    """

    def __init__(self, embedding_client: EmbeddingClient = None,
                 bm25_weight: float = 0.4, tfidf_weight: float = 0.3,
                 embed_weight: float = 0.3):
        self.bm25 = BM25Index()
        self.tfidf = TFIDFIndex()
        self.embedder = embedding_client
        self.bm25_weight = bm25_weight
        self.tfidf_weight = tfidf_weight
        self.embed_weight = embed_weight if embedding_client and embedding_client.available() else 0.0
        self._doc_embeddings: List[List[float]] = []
        self._doc_texts: List[str] = []

    def add(self, text: str, metadata: dict = None) -> int:
        """Add a single document to all indices."""
        idx = self.bm25.add(text, metadata)
        self.tfidf.add(text, metadata)
        self._doc_texts.append(text)
        return idx

    def add_batch(self, items: List[Tuple[str, dict]]) -> None:
        """Batch add documents."""
        for text, meta in items:
            self.add(text, meta)

    def index_embeddings(self, texts: List[str] = None) -> bool:
        """Pre-compute embeddings for all documents. Returns True if successful."""
        if not self.embedder or not self.embedder.available():
            return False
        source = texts or self._doc_texts
        if not source:
            return False
        embeds = self.embedder.embed(source)
        if embeds is None:
            return False
        self._doc_embeddings = embeds
        return True

    def search(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        """
        Hybrid search with RRF fusion.

        If embeddings available: BM25 + TFIDF + embeddings -> RRF
        Otherwise: BM25 + TFIDF -> weighted fusion
        """
        results: Dict[int, RetrievalResult] = {}

        # BM25 results
        for idx, score, text, meta in self.bm25.search(query, top_k * 2):
            results[idx] = RetrievalResult(text=text, score=score * self.bm25_weight,
                                           metadata=meta, source="bm25")

        # TFIDF results
        for idx, score, text, meta in self.tfidf.search(query, top_k * 2):
            if idx in results:
                results[idx].score += score * self.tfidf_weight
                results[idx].source = "hybrid"
            else:
                results[idx] = RetrievalResult(text=text, score=score * self.tfidf_weight,
                                               metadata=meta, source="tfidf")

        # Embedding results (if available)
        if self._doc_embeddings and self.embedder and self.embedder.available():
            q_embeds = self.embedder.embed([query])
            if q_embeds:
                q_vec = q_embeds[0]
                for idx, doc_vec in enumerate(self._doc_embeddings):
                    if idx >= len(self._doc_texts):
                        continue
                    sim = self._cosine(q_vec, doc_vec)
                    if sim > 0.3:  # minimum similarity threshold
                        if idx in results:
                            results[idx].score += sim * self.embed_weight
                        else:
                            results[idx] = RetrievalResult(
                                text=self._doc_texts[idx],
                                score=sim * self.embed_weight,
                                source="embedding",
                            )

        # Sort and return top_k
        sorted_results = sorted(results.values(), key=lambda r: -r.score)
        return sorted_results[:top_k]

    def search_simple(self, query: str, top_k: int = 5) -> List[str]:
        """Search and return just the text snippets."""
        return [r.text[:300] for r in self.search(query, top_k)]

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def __len__(self) -> int:
        return len(self.bm25)


# ── convenience factory ──────────────────────────────────────────────────────

def create_retriever(use_embeddings: bool = True,
                     embedding_model: str = None) -> HybridRetriever:
    """
    Factory: create a HybridRetriever with sensible defaults.

    Args:
        use_embeddings: Try to use llama.cpp embeddings if available
        embedding_model: Optional model name for embeddings
    """
    embed_client = None
    if use_embeddings:
        embed_client = EmbeddingClient(model=embedding_model)
        if not embed_client.available():
            embed_client = None

    if embed_client:
        return HybridRetriever(
            embedding_client=embed_client,
            bm25_weight=0.35,
            tfidf_weight=0.25,
            embed_weight=0.40,
        )
    else:
        return HybridRetriever(
            embedding_client=None,
            bm25_weight=0.55,
            tfidf_weight=0.45,
            embed_weight=0.0,
        )
