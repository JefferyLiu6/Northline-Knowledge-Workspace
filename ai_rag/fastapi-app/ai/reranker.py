"""Reranking.

The second failure point discussed in Chapter 13: vector similarity measures overall semantic proximity,
Not "Can this segment answer this question", so the real answer often ranks fourth and is ignored by the model.

Vector retrieval is a dual-tower model: the question and the segment are independently encoded into vectors, then the distance is calculated,
The model does not know what the user will ask when encoding the segment.

Reranking model is cross-encoding: the question and the segment are concatenated and fed into the model, directly outputting a relevance score.
It is more accurate but much slower, so it can only be used on a small number of candidates after coarse screening:

    Vector + BM25 coarse screening out 10 to 20 items -> reranking fine screening out the top 3 to 4 items

The reranking interface of BaiLian is not in OpenAI compatibility mode, the calling logic is written in model_factory in Chapter 11.
This module packages it as a BaseDocumentCompressor in LangChain,
So reranking can be used as a standard component in LangChain's retrieval pipeline.
"""

from typing import Sequence

from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document

from ai import model_factory
from common.exception_handler import CustomException
from models import AiModelConfig


class DashScopeRerank(BaseDocumentCompressor):
    """Use the configured reranker to keep the most relevant LangChain documents."""

    # BaseDocument Compressor inherited from pydantic model, field to make a statement
    config: AiModelConfig
    top_n: int = 3

    # AiModelConfig is a Tortoise model, not a pydantic type, allowing any type
    model_config = {"arbitrary_types_allowed": True}

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks = None,
    ) -> Sequence[Document]:
        """Synchronous interface. This project's entire pipeline is asynchronous, only using the following asynchronous version."""
        raise NotImplementedError("Please use acompress_documents, the calling chain of this project is asynchronous")

    async def acompress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks = None,
    ) -> Sequence[Document]:
        """Rerank the documents by their relevance to the question, keeping only the top_n."""
        if not documents:
            return []
        texts = [doc.page_content for doc in documents]
        results = await model_factory.rerank(self.config, query, texts, self.top_n)
        if not results:
            raise CustomException("The reranking interface does not return results, please check the reranking model configuration")
        ranked = []
        for item in results:
            index = item.get("index")
            # Index returned from the interface points to texts passed in and crosses the description of return structure as not expected
            if index is None or index < 0 or index >= len(documents):
                continue
            source = documents[index]
            metadata = dict(source.metadata)
            # Write the reordered correlation score into metadata, overlaying points in the rough sifting phase
            metadata["rerank_score"] = item.get("relevance_score")
            ranked.append(Document(page_content=source.page_content, metadata=metadata))
        return ranked


def to_documents(results: list[dict]) -> list[Document]:
    """Convert the retrieval results into LangChain's Document.

    page_content holds the fragment's main text, all other fields are stuffed into metadata,
    After reranking, it still relies on the chunk_id in metadata to find the original result.
    """
    documents = []
    for item in results:
        metadata = {key: value for key, value in item.items() if key != "content"}
        documents.append(Document(page_content=item["content"], metadata=metadata))
    return documents


def from_documents(documents: Sequence[Document]) -> list[dict]:
    """Convert the reranked Document back into the result dictionary of this project."""
    results = []
    for doc in documents:
        item = dict(doc.metadata)
        item["content"] = doc.page_content
        score = item.pop("rerank_score", None)
        if score is not None:
            # Reordering is the final sorting basis, overlaying the fractions of the rough sift phase.
            item["score"] = round(float(score), 6)
        # Keeps the source of the rough sift phase and then reorders it
        previous = item.get("source", "")
        item["source"] = f"{previous}→Rerank" if previous else "Rerank"
        results.append(item)
    return results
