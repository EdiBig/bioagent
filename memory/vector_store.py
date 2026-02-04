"""
RAG System with Vector Store for semantic search.

This module provides vector-based semantic search over past analyses.
It tries to use ChromaDB if available, but falls back to a simple
JSON-based store with sentence-transformers for environments where
ChromaDB cannot be installed (e.g., Python 3.14 without onnxruntime).
"""

from __future__ import annotations

import json
import uuid
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Any

from .types import RAGResult, estimate_tokens


class VectorStoreResult:
    """Result of a vector store operation."""

    def __init__(
        self,
        success: bool,
        message: str,
        results: list[RAGResult] | None = None,
        document_id: str | None = None,
    ):
        self.success = success
        self.message = message
        self.results = results or []
        self.document_id = document_id

    def to_string(self) -> str:
        """Format for Claude."""
        if not self.success:
            return f"Vector store error: {self.message}"

        if self.document_id:
            return f"Document indexed successfully (ID: {self.document_id})"

        if not self.results:
            return "No relevant results found in memory."

        lines = [f"Found {len(self.results)} relevant memory item(s):\n"]
        for i, result in enumerate(self.results, 1):
            lines.append(f"--- Result {i} (similarity: {result.similarity:.2f}) ---")
            lines.append(f"Source: {result.source}")
            if result.timestamp:
                lines.append(f"Time: {result.timestamp}")
            lines.append(f"\n{result.content}\n")

        return "\n".join(lines)


class SimpleVectorStore:
    """Simple JSON-based vector store fallback.

    Uses sentence-transformers for embeddings and stores everything
    in a JSON file with numpy arrays for vectors. Provides basic
    cosine similarity search.
    """

    def __init__(
        self,
        persist_dir: str,
        embedding_model: str = "all-MiniLM-L6-v2",
        max_results: int = 5,
        similarity_threshold: float = 0.7,
    ):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.persist_dir / "vector_index.json"
        self.vectors_file = self.persist_dir / "vectors.npy"
        self.embedding_model_name = embedding_model
        self.max_results = max_results
        self.similarity_threshold = similarity_threshold

        self._embedding_model = None
        self._documents: list[dict] = []
        self._vectors: np.ndarray | None = None
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Initialize embedding model and load data."""
        if self._initialized:
            return True

        try:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(self.embedding_model_name)
            self._load_data()
            self._initialized = True
            return True
        except ImportError:
            print("Warning: sentence-transformers not installed. RAG features disabled.")
            return False
        except Exception as e:
            print(f"Warning: Failed to initialize vector store: {e}")
            return False

    def _load_data(self) -> None:
        """Load documents and vectors from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    self._documents = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._documents = []

        if self.vectors_file.exists() and self._documents:
            try:
                self._vectors = np.load(self.vectors_file)
            except (IOError, ValueError):
                self._vectors = None

    def _save_data(self) -> None:
        """Save documents and vectors to disk."""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self._documents, f, indent=2, default=str)

        if self._vectors is not None and len(self._vectors) > 0:
            np.save(self.vectors_file, self._vectors)

    def _embed(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        return self._embedding_model.encode(texts, convert_to_numpy=True)

    def _cosine_similarity(self, query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between query and documents."""
        # Normalize vectors
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)
        doc_norms = doc_vecs / (np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-8)
        return np.dot(doc_norms, query_norm)

    def add_document(
        self,
        content: str,
        source: str,
        metadata: dict[str, Any] | None = None,
        document_id: str | None = None,
    ) -> VectorStoreResult:
        """Add a document to the store."""
        if not self._ensure_initialized():
            return VectorStoreResult(
                success=False,
                message="Vector store not available (missing dependencies)",
            )

        if not content or not content.strip():
            return VectorStoreResult(
                success=False,
                message="Cannot index empty content",
            )

        if not document_id:
            document_id = str(uuid.uuid4())

        # Generate embedding
        embedding = self._embed([content])[0]

        # Add to documents
        doc = {
            "id": document_id,
            "content": content,
            "source": source,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._documents.append(doc)

        # Add to vectors
        if self._vectors is None:
            self._vectors = embedding.reshape(1, -1)
        else:
            self._vectors = np.vstack([self._vectors, embedding])

        self._save_data()

        return VectorStoreResult(
            success=True,
            message="Document indexed",
            document_id=document_id,
        )

    def search(
        self,
        query: str,
        max_results: int | None = None,
        source_filter: str | None = None,
        min_similarity: float | None = None,
    ) -> VectorStoreResult:
        """Search for relevant documents."""
        if not self._ensure_initialized():
            return VectorStoreResult(
                success=False,
                message="Vector store not available (missing dependencies)",
            )

        if not query or not query.strip():
            return VectorStoreResult(success=True, message="Empty query", results=[])

        if self._vectors is None or len(self._documents) == 0:
            return VectorStoreResult(success=True, message="No documents indexed", results=[])

        max_results = max_results or self.max_results
        min_similarity = min_similarity or self.similarity_threshold

        # Generate query embedding
        query_vec = self._embed([query])[0]

        # Compute similarities
        similarities = self._cosine_similarity(query_vec, self._vectors)

        # Get top results
        indices = np.argsort(similarities)[::-1]

        results = []
        for idx in indices:
            sim = float(similarities[idx])
            if sim < min_similarity:
                break

            doc = self._documents[idx]

            # Apply source filter
            if source_filter and doc.get("source") != source_filter:
                continue

            results.append(RAGResult(
                id=doc["id"],
                content=doc["content"],
                similarity=sim,
                source=doc.get("source", "unknown"),
                metadata=doc.get("metadata", {}),
                timestamp=doc.get("timestamp", ""),
            ))

            if len(results) >= max_results:
                break

        return VectorStoreResult(
            success=True,
            message=f"Found {len(results)} relevant documents",
            results=results,
        )

    def is_available(self) -> bool:
        """Check if vector store is available."""
        return self._ensure_initialized()

    def get_stats(self) -> dict[str, Any]:
        """Get store statistics."""
        if not self._ensure_initialized():
            return {"initialized": False, "error": "Not available"}

        return {
            "initialized": True,
            "backend": "simple_json",
            "document_count": len(self._documents),
            "embedding_model": self.embedding_model_name,
            "persist_dir": str(self.persist_dir),
        }

    def clear(self) -> VectorStoreResult:
        """Clear all documents."""
        self._documents = []
        self._vectors = None
        self._save_data()
        return VectorStoreResult(success=True, message="Store cleared")


class VectorStore:
    """Vector store for semantic search.

    Tries to use ChromaDB if available, falls back to SimpleVectorStore.
    """

    def __init__(
        self,
        persist_dir: str,
        collection_name: str = "bioagent_memory",
        embedding_model: str = "all-MiniLM-L6-v2",
        max_results: int = 5,
        similarity_threshold: float = 0.7,
    ):
        """Initialize vector store.

        Args:
            persist_dir: Directory for persistence
            collection_name: Name of the collection (ChromaDB only)
            embedding_model: Sentence-transformers model name
            max_results: Default max results per search
            similarity_threshold: Minimum similarity for results
        """
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        self.max_results = max_results
        self.similarity_threshold = similarity_threshold

        # Try ChromaDB first, fall back to simple store
        self._backend = None
        self._backend_type = None
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Lazy initialization - try ChromaDB, fall back to simple store."""
        if self._initialized:
            return self._backend is not None

        # Try ChromaDB first
        try:
            import chromadb
            from chromadb.config import Settings
            from sentence_transformers import SentenceTransformer

            client = chromadb.PersistentClient(
                path=str(self.persist_dir / "chroma"),
                settings=Settings(anonymized_telemetry=False),
            )
            collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            embedding_model = SentenceTransformer(self.embedding_model_name)

            self._backend = {
                "client": client,
                "collection": collection,
                "embedding_model": embedding_model,
            }
            self._backend_type = "chromadb"
            self._initialized = True
            return True

        except Exception as e:
            # ChromaDB not available, try simple store
            pass

        # Fall back to simple store
        try:
            simple_store = SimpleVectorStore(
                persist_dir=str(self.persist_dir / "simple"),
                embedding_model=self.embedding_model_name,
                max_results=self.max_results,
                similarity_threshold=self.similarity_threshold,
            )
            if simple_store.is_available():
                self._backend = simple_store
                self._backend_type = "simple"
                self._initialized = True
                return True
        except Exception as e:
            print(f"Warning: Failed to initialize any vector store: {e}")

        self._initialized = True  # Mark as tried
        return False

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts."""
        if self._backend_type == "chromadb":
            embeddings = self._backend["embedding_model"].encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        return []

    def add_document(
        self,
        content: str,
        source: str,
        metadata: dict[str, Any] | None = None,
        document_id: str | None = None,
    ) -> VectorStoreResult:
        """Add a document to the vector store."""
        if not self._ensure_initialized():
            return VectorStoreResult(
                success=False,
                message="Vector store not available (missing dependencies)",
            )

        if self._backend_type == "simple":
            return self._backend.add_document(content, source, metadata, document_id)

        # ChromaDB backend
        if not content or not content.strip():
            return VectorStoreResult(success=False, message="Cannot index empty content")

        if not document_id:
            document_id = str(uuid.uuid4())

        doc_metadata = metadata or {}
        doc_metadata["source"] = source
        doc_metadata["timestamp"] = datetime.now().isoformat()
        doc_metadata["token_estimate"] = estimate_tokens(content)
        doc_metadata = {
            k: str(v) if not isinstance(v, (str, int, float, bool)) else v
            for k, v in doc_metadata.items()
        }

        try:
            embedding = self._embed([content])[0]
            self._backend["collection"].add(
                ids=[document_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[doc_metadata],
            )
            return VectorStoreResult(success=True, message="Document indexed", document_id=document_id)
        except Exception as e:
            return VectorStoreResult(success=False, message=f"Failed to index document: {e}")

    def add_tool_result(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        result: str,
        session_id: str = "",
    ) -> VectorStoreResult:
        """Index a tool execution result."""
        if len(result) < 50:
            return VectorStoreResult(success=True, message="Result too short to index")

        if len(result) > 10000:
            result = result[:10000] + "\n... (truncated)"

        content = (
            f"Tool: {tool_name}\n"
            f"Input: {json.dumps(tool_input, default=str)}\n"
            f"Result:\n{result}"
        )

        metadata = {
            "tool_name": tool_name,
            "tool_input": json.dumps(tool_input, default=str)[:1000],
            "session_id": session_id,
        }

        return self.add_document(content=content, source="tool_result", metadata=metadata)

    def add_analysis_result(
        self,
        query: str,
        result: str,
        tools_used: list[str] | None = None,
        session_id: str = "",
    ) -> VectorStoreResult:
        """Index a complete analysis result."""
        if len(result) > 15000:
            result = result[:15000] + "\n... (truncated)"

        content = f"Query: {query}\n\nAnswer:\n{result}"
        if tools_used:
            content = f"Tools used: {', '.join(tools_used)}\n{content}"

        metadata = {
            "query": query[:500],
            "tools_used": json.dumps(tools_used or []),
            "session_id": session_id,
        }

        return self.add_document(content=content, source="analysis", metadata=metadata)

    def search(
        self,
        query: str,
        max_results: int | None = None,
        source_filter: str | None = None,
        min_similarity: float | None = None,
    ) -> VectorStoreResult:
        """Search for relevant documents."""
        if not self._ensure_initialized():
            return VectorStoreResult(
                success=False,
                message="Vector store not available (missing dependencies)",
            )

        if self._backend_type == "simple":
            return self._backend.search(query, max_results, source_filter, min_similarity)

        # ChromaDB backend
        if not query or not query.strip():
            return VectorStoreResult(success=True, message="Empty query", results=[])

        max_results = max_results or self.max_results
        min_similarity = min_similarity or self.similarity_threshold

        try:
            query_embedding = self._embed([query])[0]
            where_filter = {"source": source_filter} if source_filter else None

            results = self._backend["collection"].query(
                query_embeddings=[query_embedding],
                n_results=max_results * 2,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            rag_results = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i]
                    similarity = 1 - distance

                    if similarity < min_similarity:
                        continue

                    content = results["documents"][0][i]
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}

                    rag_results.append(RAGResult(
                        id=doc_id,
                        content=content,
                        similarity=similarity,
                        source=metadata.get("source", "unknown"),
                        metadata=metadata,
                        timestamp=metadata.get("timestamp", ""),
                    ))

            rag_results = rag_results[:max_results]

            return VectorStoreResult(
                success=True,
                message=f"Found {len(rag_results)} relevant documents",
                results=rag_results,
            )

        except Exception as e:
            return VectorStoreResult(success=False, message=f"Search failed: {e}")

    def get_recent(self, limit: int = 10, source_filter: str | None = None) -> VectorStoreResult:
        """Get recent documents."""
        if not self._ensure_initialized():
            return VectorStoreResult(
                success=False,
                message="Vector store not available (missing dependencies)",
            )

        if self._backend_type == "simple":
            # Simple store doesn't have efficient recent query, return empty
            return VectorStoreResult(success=True, message="Recent not supported", results=[])

        try:
            where_filter = {"source": source_filter} if source_filter else None
            results = self._backend["collection"].get(
                limit=limit * 2,
                where=where_filter,
                include=["documents", "metadatas"],
            )

            items = []
            if results["ids"]:
                for i, doc_id in enumerate(results["ids"]):
                    content = results["documents"][i]
                    metadata = results["metadatas"][i] if results["metadatas"] else {}
                    timestamp = metadata.get("timestamp", "")
                    items.append((timestamp, RAGResult(
                        id=doc_id,
                        content=content,
                        similarity=1.0,
                        source=metadata.get("source", "unknown"),
                        metadata=metadata,
                        timestamp=timestamp,
                    )))

            items.sort(key=lambda x: x[0], reverse=True)
            rag_results = [item[1] for item in items[:limit]]

            return VectorStoreResult(
                success=True,
                message=f"Retrieved {len(rag_results)} recent documents",
                results=rag_results,
            )

        except Exception as e:
            return VectorStoreResult(success=False, message=f"Failed to get recent documents: {e}")

    def delete_document(self, document_id: str) -> VectorStoreResult:
        """Delete a document by ID."""
        if not self._ensure_initialized():
            return VectorStoreResult(
                success=False,
                message="Vector store not available (missing dependencies)",
            )

        if self._backend_type == "simple":
            return VectorStoreResult(success=False, message="Delete not supported in simple mode")

        try:
            self._backend["collection"].delete(ids=[document_id])
            return VectorStoreResult(success=True, message=f"Document {document_id} deleted")
        except Exception as e:
            return VectorStoreResult(success=False, message=f"Failed to delete document: {e}")

    def clear(self) -> VectorStoreResult:
        """Clear all documents from the collection."""
        if not self._ensure_initialized():
            return VectorStoreResult(
                success=False,
                message="Vector store not available (missing dependencies)",
            )

        if self._backend_type == "simple":
            return self._backend.clear()

        try:
            self._backend["client"].delete_collection(self.collection_name)
            self._backend["collection"] = self._backend["client"].create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            return VectorStoreResult(success=True, message="Collection cleared")
        except Exception as e:
            return VectorStoreResult(success=False, message=f"Failed to clear collection: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get vector store statistics."""
        if not self._ensure_initialized():
            return {"initialized": False, "error": "Vector store not available"}

        if self._backend_type == "simple":
            return self._backend.get_stats()

        try:
            count = self._backend["collection"].count()
            return {
                "initialized": True,
                "backend": "chromadb",
                "collection_name": self.collection_name,
                "document_count": count,
                "embedding_model": self.embedding_model_name,
                "persist_dir": str(self.persist_dir),
            }
        except Exception as e:
            return {"initialized": True, "error": str(e)}

    def is_available(self) -> bool:
        """Check if vector store is available."""
        return self._ensure_initialized() and self._backend is not None
