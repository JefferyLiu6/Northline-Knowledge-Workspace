"""Text splitting.

Split the entire text parsed in Chapter 07 into small fragments. Fragments are the smallest retrieval unit in RAG,
if split too large, a fragment may contain several topics, and even if it is retrieved, it can't answer precisely;
if split too small, a sentence may be cut in half, and the model can't see the complete semantic meaning.

This module provides two strategies:

    Recursive Chunking   Split recursively by delimiter until the target length is reached, commonly used for general scenarios
    Parent-Child Chunking   First split into large parent chunks, then split each parent chunk into smaller child chunks
               Compare using child chunks during retrieval, and provide the entire parent chunk to the model upon hit
               Balance "smaller chunks for more accurate retrieval" and "larger chunks for more complete context during generation"

All outputs are a list of Chunk objects, with parent chunks appearing before their child chunks in the list
When writing to the database, first insert the parent chunk to get an ID, then fill the parent_id field in the child chunks
"""

import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Chapter 07 PDF parsing is written at the beginning of each page. Page numbers are presented here to record the session
PAGE_PATTERN = re.compile(r"\[Page\s+(\d+)\]|\u3010\u7b2c\s*(\d+)\s*\u9875\u3011")

# The transliteration method in the separator. The data store is a visible character \n, which must be restored to a real line break
ESCAPES = {"\\n": "\n", "\\t": "\t"}


@dataclass
class Chunk:
    """A single segment to be stored in the database"""

    content: str
    # Normal block / parent block / sub-block
    chunk_type: str = "Standard chunk"
    # Order numbers in documents, separate numbers for each parent and sub-block
    chunk_index: int = 0
    # a block that points it to the parent in the return list, and the parent and normal block are None
    parent_index: int | None = None
    page_no: int | None = None


def parse_separators(raw: str | None) -> list[str]:
    """Recover a list from a comma-separated delimiter string stored in the database

    The database stores visible characters like `\\n\\n,\\n,.,!,?`
    These characters cannot be directly used for splitting to match actual line breaks; they need to be restored first
    """
    if not raw:
        # Use paragraph, sentence, and whitespace boundaries by default.
        return ["\n\n", "\n", ". ", "! ", "? ", "\u3002", "\uff01", "\uff1f", "\uff1b", "\uff0c", " ", ""]
    items = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        for escaped, real in ESCAPES.items():
            text = text.replace(escaped, real)
        items.append(text)
    # Add an empty string at the end to ensure that any longer consecutive text can be forcibly cut
    if "" not in items:
        items.append("")
    return items


def _page_no_of(text: str, fallback: int | None) -> int | None:
    """Extract page number markers from the text segment; if not found, use the page number from the previous segment

    The latter segment may not contain [page N] prefix, which must be the page on which the previous mark is placed.
    """
    matched = PAGE_PATTERN.search(text)
    if matched:
        return int(matched.group(1) or matched.group(2))
    return fallback


def _split_recursive(text: str, chunk_size: int, chunk_overlap: int, separators: list[str]) -> list[str]:
    """Split recursively by delimiter

    RecursiveCharacterTextSplitter first splits using the first delimiter
    If the resulting chunk is still too long, it switches to the next delimiter and continues splitting until the target length is reached
    This approach ensures splitting at natural boundaries like paragraphs and sentences, rather than cutting in the middle of a sentence
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        # Measure chunk length in characters rather than estimated tokens.
        length_function=len,
        # Keep the separator, stop the question mark at the end of the sentence. Read it.
        keep_separator=True,
    )
    return [piece.strip() for piece in splitter.split_text(text) if piece.strip()]


def split_by_recursive(text: str, chunk_size: int, chunk_overlap: int, separators: list[str]) -> list[Chunk]:
    """Recursive Chunking: Split the entire text into a group of parallel regular chunks"""
    chunks = []
    page_no = None
    for index, piece in enumerate(_split_recursive(text, chunk_size, chunk_overlap, separators)):
        page_no = _page_no_of(piece, page_no)
        chunks.append(
            Chunk(content=piece, chunk_type="Standard chunk", chunk_index=index, page_no=page_no)
        )
    return chunks


def split_by_parent_child(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    parent_chunk_size: int,
    separators: list[str],
) -> list[Chunk]:
    """Parent-Child Chunking: First split parent chunks, then split each parent chunk into child chunks

    The returned list has parent chunks and their child chunks adjacent to each other, with the child chunk's parent_index pointing to the index of the parent chunk in the list
    """
    chunks: list[Chunk] = []
    page_no = None
    parent_index = 0
    child_index = 0
    # The parent block uses a cut without overlap, and the parent block overlaps with each other, causing large repetitions in the context of the refilled model.
    parents = _split_recursive(text, parent_chunk_size, 0, separators)
    for parent_text in parents:
        page_no = _page_no_of(parent_text, page_no)
        parent_position = len(chunks)
        chunks.append(
            Chunk(
                content=parent_text,
                chunk_type="Parent chunk",
                chunk_index=parent_index,
                page_no=page_no,
            )
        )
        parent_index += 1
        for child_text in _split_recursive(parent_text, chunk_size, chunk_overlap, separators):
            chunks.append(
                Chunk(
                    content=child_text,
                    chunk_type="Child chunk",
                    chunk_index=child_index,
                    parent_index=parent_position,
                    page_no=_page_no_of(child_text, page_no),
                )
            )
            child_index += 1
    return chunks


def split(text: str, strategy: dict) -> list[Chunk]:
    """Split text according to the configured strategy

    strategy comes from the chunk_strategy table, with fields and table structure matching one-to-one
    """
    separators = parse_separators(strategy.get("separators"))
    chunk_size = strategy.get("chunk_size") or 500
    chunk_overlap = strategy.get("chunk_overlap") or 0
    strategy_type = strategy.get("strategy_type")
    if strategy_type == "Parent-child chunking":
        parent_chunk_size = strategy.get("parent_chunk_size") or chunk_size * 4
        return split_by_parent_child(text, chunk_size, chunk_overlap, parent_chunk_size, separators)
    if strategy_type == "Recursive chunking":
        return split_by_recursive(text, chunk_size, chunk_overlap, separators)
    raise ValueError(f"No Corresponding {strategy_type} Split Implementation of")
