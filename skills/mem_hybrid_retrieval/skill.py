"""
mem_hybrid_retrieval — Zero-Dependency Hybrid Retrieval Memory

Replaces ChromaDB-based core_memory_rag with BM25 + TF-IDF hybrid retrieval.
No external dependencies: no ChromaDB, no sentence-transformers, no API keys.

Optional: llama.cpp embeddings (localhost:61183/v1/embeddings) for semantic search.
Falls back to pure BM25+TFIDF if embedding server unavailable.

Hooks:
  on_before_scene_write: inject relevant past context into writing prompt
  on_after_scene_write: index new chapter content for future retrieval
"""

from pathlib import Path
from typing import Optional, List

from core.base_skill import BaseSkill
from utils.hybrid_retrieval import HybridRetriever, create_retriever


class MemHybridRetrievalSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "混合检索引擎"
        self.retriever: Optional[HybridRetriever] = None
        self._index_built = False
        self._chapter_cache: List[str] = []

    def on_init(self) -> None:
        self.retriever = create_retriever(use_embeddings=True)
        emb_status = "with embeddings" if self.retriever.embedder else "BM25+TFIDF only"
        print(f"  [OK] {self.name} ready ({emb_status}, {len(self.retriever)} docs indexed)")

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        """Inject relevant past context into the writing prompt."""
        chapter_id = beat_data.get("chapter_id") or self.context.current_chapter_id

        # Build retrieval context from chapter outline
        outline = beat_data.get("overview", "")
        title = beat_data.get("title", "")
        query = f"{title} {outline}" if title or outline else f"chapter {chapter_id}"

        # Search for relevant past content
        results = self.retriever.search(query, top_k=5)
        if not results:
            return prompt_payload

        context_parts = ["\n[RAG Retrieval — Relevant past content]\n"]
        for i, r in enumerate(results[:5], 1):
            snippet = r.text[:400].replace("\n", " ")
            context_parts.append(f"  [{i}] (score:{r.score:.2f}, {r.source}) {snippet}...")

        prompt_payload.append("\n".join(context_parts))
        return prompt_payload

    def on_after_scene_write(self, beat_data: dict, raw_text: str) -> None:
        """Index new chapter content for future retrieval."""
        if not raw_text or len(raw_text.strip()) < 100:
            return

        chapter_id = beat_data.get("chapter_id", 0)

        # Chunk the text into paragraphs (sliding window)
        chunks = self._chunk_text(raw_text, chunk_size=500, overlap=100)
        for i, chunk in enumerate(chunks):
            self.retriever.add(chunk, {
                "chapter_id": chapter_id,
                "chunk_index": i,
                "type": "chapter_content",
            })
            self._chapter_cache.append(chunk)

        # Limit cache size (keep last 200 chunks)
        if len(self._chapter_cache) > 200:
            self._chapter_cache = self._chapter_cache[-200:]

        if not self._index_built and len(self.retriever) >= 10:
            self._try_build_embeddings()

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks by paragraph boundaries."""
        paragraphs = text.split('\n')
        chunks = []
        current = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) > chunk_size:
                if current:
                    chunks.append(current)
                    # Keep overlap
                    overlap_text = current[-overlap:] if len(current) > overlap else current
                    current = overlap_text + "\n" + para
                else:
                    chunks.append(para[:chunk_size])
            else:
                current = current + "\n" + para if current else para
        if current:
            chunks.append(current)
        return chunks

    def _try_build_embeddings(self) -> None:
        """Try to index embeddings for all stored chunks."""
        if not self.retriever.embedder or not self.retriever.embedder.available():
            return
        try:
            texts = [r.text for r in self.retriever.search("")] if False else self._chapter_cache[-50:]
            if self.retriever.index_embeddings(texts):
                self._index_built = True
                print(f"  [OK] {self.name}: {len(texts)} embeddings indexed")
        except Exception as e:
            print(f"  [!] {self.name}: embedding indexing failed: {e}")

    def search(self, query: str, top_k: int = 10) -> list:
        """Public API: search for relevant content."""
        if not self.retriever:
            return []
        results = self.retriever.search(query, top_k)
        return [{"text": r.text, "score": r.score, "source": r.source,
                 "metadata": r.metadata} for r in results]
