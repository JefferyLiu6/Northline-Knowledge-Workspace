"""Find stale derived vectors; pass --apply to remove them and mark chunks pending."""
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tortoise import Tortoise
from settings import TORTOISE_ORM
from models import KnowledgeChunk,KnowledgeDocument
from ai import vector_store

async def run(apply):
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        chunks={c.id:c for c in await KnowledgeChunk.all()}
        connection=await vector_store._connect()
        async with connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT chunk_id,document_id,kb_id,content FROM knowledge_chunk_vector")
                rows=await cursor.fetchall()
        stale=[row[0] for row in rows if row[0] not in chunks or
               (chunks[row[0]].document_id,chunks[row[0]].kb_id,chunks[row[0]].content)!=tuple(row[1:])]
        if apply and stale:
            await vector_store.delete_by_chunk_ids(stale)
            await KnowledgeChunk.filter(id__in=stale).update(vector_status="Pending embedding")
            ids={chunks[i].document_id for i in stale if i in chunks}
            await KnowledgeDocument.filter(id__in=list(ids)).update(vector_status="Pending embedding")
        print(json.dumps({"vectors":len(rows),"stale_chunk_ids":stale,"applied":apply}))
    finally:
        await Tortoise.close_connections()
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--apply",action="store_true")
    asyncio.run(run(p.parse_args().apply))
