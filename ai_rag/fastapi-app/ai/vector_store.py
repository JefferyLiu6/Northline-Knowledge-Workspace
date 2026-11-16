"""Vector database read and write

Vectors are stored in the PostgreSQL knowledge_chunk_vector table, while business data remains in MySQL
The two databases are linked via chunk_id: the chunk_id here is the same as knowledge_chunk.id in MySQL

Do not use langchain_postgres's PGVector wrapper, as it would create tables according to its own conventions
While the vector table for this project is created in Chapter 10 using ai_rag_vector.sql, it includes kb_id and chunk_type
These columns are used for metadata filtering. Directly writing SQL with psycopg, the table structure is fully under our control.
"""

import psycopg
from pgvector.psycopg import Vector, register_vector_async

from common.exception_handler import CustomException
from settings import PGVECTOR


def _dsn() -> str:
    """Construct the PostgreSQL connection string based on the configuration in settings.py."""
    return (
        f"host={PGVECTOR['host']} port={PGVECTOR['port']} dbname={PGVECTOR['database']} "
        f"user={PGVECTOR['user']} password={PGVECTOR['password']}"
    )


async def _connect() -> psycopg.AsyncConnection:
    """Open a connection to the vector database and register the vector type.

    register_vector_async allows psycopg to recognize the vector type,
    Without registration, passing a Python list would be treated as an array type, leading to an insertion error.
    """
    try:
        connection = await psycopg.AsyncConnection.connect(_dsn())
    except Exception as exc:
        raise CustomException(f"Cannot Connect to Vector Database, Please Confirm PostgreSQL is Running:{str(exc)[:200]}")
    await register_vector_async(connection)
    return connection


async def upsert(rows: list[dict]) -> int:
    """Write or overwrite a batch of chunk vectors.

    The table has a unique index on chunk_id, so when vectorizing the same batch of chunks repeatedly, it will overwrite by chunk_id,
    Preventing duplicate insertions, so it can be executed repeatedly without prior deletion.
    """
    if not rows:
        return 0
    sql = """
        insert into knowledge_chunk_vector
            (chunk_id, kb_id, document_id, parent_chunk_id, chunk_type, title_path, content, embedding)
        values
            (%(chunk_id)s, %(kb_id)s, %(document_id)s, %(parent_chunk_id)s,
             %(chunk_type)s, %(title_path)s, %(content)s, %(embedding)s)
        on conflict (chunk_id) do update set
            kb_id = excluded.kb_id,
            document_id = excluded.document_id,
            parent_chunk_id = excluded.parent_chunk_id,
            chunk_type = excluded.chunk_type,
            title_path = excluded.title_path,
            content = excluded.content,
            embedding = excluded.embedding,
            update_time = current_timestamp
    """
    connection = await _connect()
    async with connection:
        async with connection.cursor() as cursor:
            await cursor.executemany(sql, rows)
        await connection.commit()
    return len(rows)


async def delete_by_document(document_id: int) -> int:
    """Delete all vectors for a document. Called when a document is deleted or re-splitted."""
    connection = await _connect()
    async with connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "delete from knowledge_chunk_vector where document_id = %s", (document_id,)
            )
            deleted = cursor.rowcount
        await connection.commit()
    return deleted


async def delete_by_chunk_ids(chunk_ids: list[int]) -> int:
    """Delete the vector for a specific chunk. Called when a chunk is manually deleted."""
    if not chunk_ids:
        return 0
    connection = await _connect()
    async with connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "delete from knowledge_chunk_vector where chunk_id = any(%s)", (chunk_ids,)
            )
            deleted = cursor.rowcount
        await connection.commit()
    return deleted


async def delete_by_kb(kb_id: int) -> int:
    """Delete all vectors for a knowledge base. Called when a full rebuild of the vector model is needed."""
    connection = await _connect()
    async with connection:
        async with connection.cursor() as cursor:
            await cursor.execute("delete from knowledge_chunk_vector where kb_id = %s", (kb_id,))
            deleted = cursor.rowcount
        await connection.commit()
    return deleted


async def count_by_kb(kb_id: int) -> int:
    """Count the number of chunks already written into the vector database for a knowledge base."""
    connection = await _connect()
    async with connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "select count(*) from knowledge_chunk_vector where kb_id = %s", (kb_id,)
            )
            row = await cursor.fetchone()
    return row[0] if row else 0


async def search(
    kb_ids: list[int],
    embedding: list[float],
    top_k: int = 5,
    document_ids: list[int] | None = None,
    chunk_types: list[str] | None = None,
) -> list[dict]:
    """Retrieve the most similar chunks based on cosine distance.

    kb_ids, document_ids, and chunk_types are metadata filtering conditions,
    They are combined with the vector comparison in the same SQL statement. The database first narrows down the scope based on conditions before calculating the distance,
    No need to calculate the distance for the entire table and then filter again in MySQL.

    The returned score is similarity, derived from the distance. The larger the score, the more similar, with a range of 0 to 1.
    """
    if not kb_ids:
        return []
    conditions = ["kb_id = any(%(kb_ids)s)"]
    # Query vectors must be packed on the first floor of Vector retransmit.
    # The list of Python is fine because it's written in the vector (1024) column.
    # The database can extrapolate from the column type; here the vector is the number of < = > operators.
    # There's no context on either side. Naked lists are considered float8[], directly reported.
    # operator does not exist: vector <=> double precision[].
    params: dict = {"kb_ids": kb_ids, "embedding": Vector(embedding), "top_k": top_k}
    if document_ids:
        conditions.append("document_id = any(%(document_ids)s)")
        params["document_ids"] = document_ids
    if chunk_types:
        # Father and son are divided into repositories that only retrieve sub-blocks, leaving them to fill in after they've been hit.
        conditions.append("chunk_type = any(%(chunk_types)s)")
        params["chunk_types"] = chunk_types
    where = " and ".join(conditions)
    sql = f"""
        select chunk_id, kb_id, document_id, parent_chunk_id, chunk_type, title_path, content,
               embedding <=> %(embedding)s as distance
        from knowledge_chunk_vector
        where {where}
        order by embedding <=> %(embedding)s
        limit %(top_k)s
    """
    connection = await _connect()
    async with connection:
        async with connection.cursor() as cursor:
            await cursor.execute(sql, params)
            rows = await cursor.fetchall()
    results = []
    for row in rows:
        distance = float(row[7])
        results.append(
            {
                "chunk_id": row[0],
                "kb_id": row[1],
                "document_id": row[2],
                "parent_chunk_id": row[3],
                "chunk_type": row[4],
                "title_path": row[5],
                "content": row[6],
                # The cosine range is 0 to 2,1 minus the distance gets similarity.
                # Show similarities on the page as opposed to intuitive: the bigger the number, the more relevant
                "score": round(1 - distance, 6),
                "source": "Vector search",
            }
        )
    return results


async def health_check() -> str:
    """Connectivity check for page display of vector database status."""
    connection = await _connect()
    async with connection:
        async with connection.cursor() as cursor:
            await cursor.execute("select count(*) from knowledge_chunk_vector")
            row = await cursor.fetchone()
    return f"Vector Database Connection is Normal, Currently {row[0] if row else 0} Vectors"
