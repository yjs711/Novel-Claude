import os
import re
import json
from difflib import SequenceMatcher
from typing import List

import chromadb
import ahocorasick
from chromadb.utils import embedding_functions

from core.base_skill import BaseSkill
from core.novel_context import NovelContext
from utils.config import MEMORY_DIR, SETTINGS_DIR, register_background_task
from utils.llm_client import _get_client as get_llm_client, resolve_model, resolve_provider


# ── 本地 Embedding 回退 ────────────────────────────────────────────────────────
_LOCAL_EMBED_MODEL = None


def _get_local_embedding_model():
    """延迟加载本地 embedding 模型（首次调用时下载，之后缓存）。"""
    global _LOCAL_EMBED_MODEL
    if _LOCAL_EMBED_MODEL is not None:
        return _LOCAL_EMBED_MODEL
    try:
        from sentence_transformers import SentenceTransformer
        # paraphrase-multilingual-MiniLM-L12-v2: 多语言，384维，~420MB
        _LOCAL_EMBED_MODEL = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2",
            device="cpu"  # 避免抢 GPU 推理资源
        )
        print("  [✓] 本地 embedding 模型已加载 (paraphrase-multilingual-MiniLM-L12-v2)")
    except ImportError:
        print("  [!] sentence-transformers 未安装，本地 embedding 不可用。安装: pip install sentence-transformers")
        _LOCAL_EMBED_MODEL = False
    except Exception as e:
        print(f"  [!] 本地 embedding 加载失败: {e}")
        _LOCAL_EMBED_MODEL = False
    return _LOCAL_EMBED_MODEL


class ZhipuEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self):
        _api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
        self.client = None
        if _api_key:
            try:
                from zhipuai import ZhipuAI
                self.client = ZhipuAI(api_key=_api_key)
            except ImportError:
                pass

    def __call__(self, input: list[str]) -> list[list[float]]:
        # 优先 Zhipu API
        if self.client:
            try:
                embeddings = []
                for text in input:
                    res = self.client.embeddings.create(model="embedding-3", input=text)
                    embeddings.append(res.data[0].embedding)
                return embeddings
            except Exception:
                pass  # fall through to local

        # 本地回退
        model = _get_local_embedding_model()
        if model:
            return model.encode(input, normalize_embeddings=True).tolist()

        raise RuntimeError("无可用 embedding 引擎：Zhipu API 不可用且本地 sentence-transformers 未安装")

class CoreMemoryRagSkill(BaseSkill):
    """
    原 s04_memory_rag.py 的能力插件化实现。
    负责在生成前检索记忆（on_before_scene_write），以及在生成后将文本切块向量入库（on_after_scene_write）。
    """
    def __init__(self, context: NovelContext):
        super().__init__(context)
        self.name = "CoreMemoryRagSkill"
        self.chroma_client = None
        self.collection = None
        self.automaton = None

    def on_init(self) -> None:
        self.chroma_client = chromadb.PersistentClient(path=MEMORY_DIR)
        emb_fn = ZhipuEmbeddingFunction()
        self.collection = self.chroma_client.get_or_create_collection(name="novel_memory", embedding_function=emb_fn)
        self.automaton = self._build_entity_automaton()

    def _build_entity_automaton(self):
        A = ahocorasick.Automaton()
        entities = []
        
        char_path = os.path.join(SETTINGS_DIR, "main_characters.json")
        if os.path.exists(char_path):
            with open(char_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for c in data.get("characters", []):
                    entities.append(c["name"])
                    
        fac_path = os.path.join(SETTINGS_DIR, "factions.json")
        if os.path.exists(fac_path):
            with open(fac_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for fac in data.get("factions", []):
                    entities.append(fac.get("name", ""))
                    
        for idx, entity in enumerate(set(entities)):
            if entity.strip():
                A.add_word(entity, (idx, entity))
                
        A.make_automaton()
        return A

    def _extract_entities_fast(self, text: str) -> list:
        if not text or not self.automaton:
            return []
        found = [item[1][1] for item in self.automaton.iter(text)]
        return list(set(found))

    def _condense_state(self, entity: str, context_chunks: list[str]) -> str:
        prompt = f"你是一个情报总结官。根据以下小说文本片段，极简总结实体【{entity}】的最新状态（例如：伤势、法宝受损情况、对其余人物的恨意等）。不要编造，如果文本没提就回复“状态正常”。\n\n" + "\n\n---\n\n".join(context_chunks)
        messages = [{"role": "user", "content": prompt}]
        client = get_llm_client()
        model = resolve_model(resolve_provider())
        res = client.chat.completions.create(model=model, messages=messages, temperature=0.1)
        return res.choices[0].message.content.strip()

    def on_before_scene_write(self, prompt_payload: List[str], beat_data: dict) -> List[str]:
        entities = self._extract_entities_fast(beat_data.get('plot_summary', ''))
        if not entities:
            return prompt_payload

        try:
            from rich.console import Console
            Console().print(f"[bold cyan]  [Memory Bus][/bold cyan] 嗅探到关键实体: {entities}，正在检索最新状态...")
        except Exception:
            print(f"  [Memory Bus] 嗅探到关键实体: {entities}，正在检索最新状态...")

        # 获取 mem_fact_summary 已注入的 L2 摘要内容，用于去重
        existing_summaries = self._get_fact_summary_text(prompt_payload)

        recent_memories = []
        for entity in entities:
            # ── 1. 关键词精确匹配（短实体名优先） ──
            keyword_docs = []
            if len(entity) <= 4:
                try:
                    all_docs = self.collection.get()
                    if all_docs and all_docs.get('documents'):
                        for doc, meta in zip(all_docs['documents'], all_docs['metadatas']):
                            if entity in doc:
                                keyword_docs.append((doc, meta))
                except Exception:
                    pass

            # ── 2. 向量语义搜索 ──
            try:
                results = self.collection.query(
                    query_texts=[entity],
                    n_results=5
                )
                vec_docs = []
                if results and results['documents'] and len(results['documents'][0]) > 0:
                    vec_docs = list(zip(results['documents'][0], results['metadatas'][0]))
            except Exception:
                vec_docs = []

            # ── 3. 合并去重：关键词匹配排在前面 ──
            seen_texts = set()
            combined = []
            for doc, meta in keyword_docs:
                key = doc[:80]  # 用前80字做去重指纹
                if key not in seen_texts:
                    seen_texts.add(key)
                    combined.append((doc, meta, "keyword"))
            for doc, meta in vec_docs:
                key = doc[:80]
                if key not in seen_texts:
                    seen_texts.add(key)
                    combined.append((doc, meta, "vector"))

            combined.sort(key=lambda x: x[1].get('chapter_id', 0), reverse=True)

            # ── 4. 与 mem_fact_summary 去重 ──
            recent_chunks = []
            for doc, _, source in combined:
                if self._is_duplicate_with_summary(doc, existing_summaries, threshold=0.7):
                    continue
                recent_chunks.append(doc)
                if len(recent_chunks) >= 3:
                    break

            if recent_chunks:
                condensed = self._condense_state(entity, recent_chunks)
                if condensed and "状态正常" not in condensed:
                    recent_memories.append(f"- {entity}: {condensed}")

        if recent_memories:
            xml_memory = "<recent_memory>\n[实体最新状态同步]\n"
            xml_memory += "\n".join(recent_memories)
            xml_memory += "\n</recent_memory>\n"
            prompt_payload.append(xml_memory)

        return prompt_payload

    def _get_fact_summary_text(self, payload: list) -> str:
        """提取 mem_fact_summary 已经注入的 L2 摘要文本，用于去重。"""
        for item in payload:
            if isinstance(item, str) and ("L2" in item or "情景记忆" in item or "Episodic Memory" in item):
                return item
        return ""

    def _is_duplicate_with_summary(self, chunk: str, summary: str, threshold: float = 0.7) -> bool:
        """检查 chunk 是否与 summary 内容重复（基于序列匹配相似度）。"""
        if not summary or not chunk:
            return False
        # 只比对前200字，节省计算
        ratio = SequenceMatcher(None, chunk[:200], summary[:200]).ratio()
        return ratio > threshold

    def on_after_scene_write(self, beat_data: dict, raw_text: str) -> None:
        chapter_id = self.context.current_chapter_id
        # 使用 EventBus 触发后台记录
        register_background_task(self._background_update_task, chapter_id, raw_text)

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
        """
        滑动窗口切块：chunk_size 中文字符，overlap 重叠字符。
        优先在句号/问号/感叹号处断句，保证语义完整。
        """
        if len(text) <= chunk_size:
            return [text]

        # 按句子边界分割
        sentences = re.split(r'(?<=[。！？\n])', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current = ""
        for s in sentences:
            if len(current) + len(s) <= chunk_size:
                current += s
            else:
                if current:
                    chunks.append(current)
                # 滑动窗口：保留最后 overlap 字符
                if len(current) > overlap:
                    current = current[-overlap:] + s
                else:
                    current = s
        if current.strip():
            chunks.append(current)
        return chunks

    def _background_update_task(self, chapter_id: int, final_content: str):
        try:
            from rich.console import Console
            Console().print(f"[dim]  [Background Task] 正在将第 {chapter_id} 章内容向量化并入库...[/dim]")
        except Exception:
            print(f"  [Background Task] 正在将第 {chapter_id} 章内容向量化并入库...")
            
        try:
            chunks = self.chunk_text(final_content)
            ids = []
            documents = []
            metadatas = []
            
            for i, chunk in enumerate(chunks):
                chunk_entities = self._extract_entities_fast(chunk)
                involved = ",".join(chunk_entities) if chunk_entities else ""
                documents.append(chunk)
                ids.append(f"ch_{chapter_id}_chunk_{i}")
                metadatas.append({
                    "chapter_id": chapter_id,
                    "involved_entities": involved
                })
                    
            if documents:
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
        except Exception as e:
            print(f"[WARN] 后台向量化任务失败 (Ch_{chapter_id}): {e}")
