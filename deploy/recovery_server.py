"""Deterministic test pauses before parse completion / after partial split or embed."""
import asyncio, os, sys, time
sys.path.insert(0, "/app")
from ai import loader, model_factory
from models import KnowledgeChunk
import uvicorn

stage = os.environ["RECOVERY_TEST_STAGE"]
if stage == "parse":
    original = loader.parse
    def parse(*args, **kwargs):
        time.sleep(120)
        return original(*args, **kwargs)
    loader.parse = parse
elif stage == "split":
    original = KnowledgeChunk.create
    count = 0
    async def create(cls, *args, **kwargs):
        global count
        result = await original(*args, **kwargs)
        count += 1
        if count == 3:
            await asyncio.sleep(120)
        return result
    KnowledgeChunk.create = classmethod(create)
elif stage == "embed":
    original = model_factory.build_embeddings
    class PausedEmbeddings:
        def __init__(self, delegate):
            self.delegate, self.calls = delegate, 0
        def __getattr__(self, name):
            return getattr(self.delegate, name)
        async def aembed_documents(self, texts):
            self.calls += 1
            if self.calls == 2:
                await asyncio.sleep(120)
            return await self.delegate.aembed_documents(texts)
    model_factory.build_embeddings = lambda config: PausedEmbeddings(original(config))
else:
    raise RuntimeError("Unknown recovery test stage")
uvicorn.run("main:app", host="0.0.0.0", port=9090)
