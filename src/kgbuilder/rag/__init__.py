"""Standard RAG Pipeline - Baseline for benchmarking.

Simple dense vector retrieval + LLM generation.

See Planning/FUSIONRAG_INTEGRATION.md Section 1 for design.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import ollama

from kgbuilder.core import get_base_url

logger = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    """Response from RAG pipeline."""

    answer: str
    retrieved_docs: list[dict[str, Any]]
    retrieval_time_ms: float | None = None
    generation_time_ms: float | None = None
    confidence: float = 0.5  # Confidence in answer


class StandardRAGPipeline:
    """Basic RAG using dense vector retrieval + LLM generation.

    Serves as baseline for comparing against more complex approaches.
    Uses ollama.embed for query embeddings and ollama provider for generation.
    """

    def __init__(
        self,
        vector_store: Any,  # QdrantStore
        llm_provider: Any,  # OllamaProvider
        top_k: int = 5,
        embedding_model: str = "qwen3-embedding",
        ollama_base_url: str | None = None,
    ) -> None:
        """Initialize standard RAG pipeline.

        Args:
            vector_store: Vector store for retrieval (Qdrant)
            llm_provider: LLM provider for answer generation (OllamaProvider)
            top_k: Number of documents to retrieve
            embedding_model: Ollama embedding model name
            ollama_base_url: Ollama API base URL
        """
        self.vector_store = vector_store
        self.llm = llm_provider
        self.top_k = top_k
        self.embedding_model = embedding_model
        self.ollama_base_url = get_base_url(ollama_base_url)

        # Initialize Ollama client
        self.ollama_client = ollama.Client(host=self.ollama_base_url)

        logger.info(
            "standard_rag_pipeline_initialized",
            vector_store=type(vector_store).__name__,
            llm_model=llm_provider.model,
            embedding_model=embedding_model,
        )

    def retrieve(self, query: str) -> list[dict[str, Any]]:
        """Retrieve relevant documents for query.

        Args:
            query: Query text

        Returns:
            List of retrieved documents with scores
        """
        try:
            # Embed query using Ollama
            response = self.ollama_client.embed(
                model=self.embedding_model,
                input=query,
            )
            query_embedding = np.array(
                response.embeddings[0] if response.embeddings else [],
                dtype=np.float32,
            )

            # Search vector store
            results = self.vector_store.search(query_embedding, top_k=self.top_k)

            # Convert results from (id, score, metadata) tuples
            documents = []
            for result_id, score, metadata in results:
                documents.append({
                    "id": result_id,
                    "content": metadata.get("content", "") if metadata else "",
                    "score": float(score),
                    "metadata": metadata or {},
                })

            logger.info(
                "retrieval_complete",
                query_len=len(query),
                results_count=len(documents),
            )
            return documents

        except Exception as e:
            logger.exception("retrieval_failed", exc_info=True)
            return []

    def generate(self, query: str, context: list[dict[str, Any]]) -> str:
        """Generate answer from retrieved context.

        Args:
            query: Original query
            context: Retrieved documents

        Returns:
            Generated answer text
        """
        try:
            # Format context
            context_text = "\n\n".join(
                [f"Document {i+1}:\n{doc['content']}" for i, doc in enumerate(context)]
            )

            # Generate with LLM
            prompt = f"""Answer the following question based on the provided documents.

Documents:
{context_text}

Question: {query}

Answer:"""

            answer = self.llm.generate(prompt, max_tokens=500)
            logger.info("generation_complete", answer_len=len(answer))
            return answer

        except Exception as e:
            logger.error("generation_failed")
            return "Error generating response"

    def answer(self, query: str) -> RAGResponse:
        """End-to-end RAG: retrieve and generate answer.

        Args:
            query: User query

        Returns:
            RAGResponse with answer and metadata
        """
        import time

        try:
            # Retrieve
            start_retrieval = time.time()
            docs = self.retrieve(query)
            retrieval_time = (time.time() - start_retrieval) * 1000

            # Generate
            start_generation = time.time()
            answer = self.generate(query, docs)
            generation_time = (time.time() - start_generation) * 1000

            # Compute confidence (simple heuristic)
            avg_score = (
                sum(d["score"] for d in docs) / len(docs) if docs else 0.0
            )

            logger.info(
                "rag_complete",
                retrieval_ms=retrieval_time,
                generation_ms=generation_time,
                confidence=avg_score,
            )

            return RAGResponse(
                answer=answer,
                retrieved_docs=docs,
                retrieval_time_ms=retrieval_time,
                generation_time_ms=generation_time,
                confidence=avg_score,
            )

        except Exception as e:
            logger.exception("rag_failed", exc_info=True)
            return RAGResponse(
                answer="Error processing query",
                retrieved_docs=[],
                confidence=0.0,
            )


__all__ = ["StandardRAGPipeline", "RAGResponse"]
