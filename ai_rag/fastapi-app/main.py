import asyncio
import sys
from contextlib import asynccontextmanager

import jieba
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import RegisterTortoise, tortoise_exception_handlers

from api import api_router
from common.exception_handler import setup_exceptions
from common.result import Result
from settings import TORTOISE_ORM
from common.runtime_lease import backend_lease


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize keyword search and open the database connection."""
    # Load the tokenizer dictionary at startup so the first BM25 search does not stall.
    await asyncio.to_thread(jieba.initialize)
    async with backend_lease():
        async with RegisterTortoise(app, config=TORTOISE_ORM):
            from common.passwords import migrate_passwords
            from service.job_recovery_service import migrate_task_context, recover_interrupted
            await migrate_task_context()
            await migrate_passwords()
            await recover_interrupted()
            yield


app = FastAPI(
    title="AI RAG Knowledge Base Platform",
    lifespan=lifespan,
    # Let Tortoise handle ORM errors such as missing rows and unique key conflicts.
    exception_handlers=tortoise_exception_handlers(),
)

# Configure coRS across domains. The front end runs at port 5173, backend at 9090, is a cross-domain request.
# If it doesn't work, the browser will block all interface calls.
app.add_middleware(
    CORSMiddleware,
    # Allow All Sources
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    # Allow all HTTP methods
    allow_methods=["*"],
    # Allow the custom token request header.
    allow_headers=["*"],
)

# Register all business routes
app.include_router(api_router)
# Register application exception handlers.
setup_exceptions(app)


@app.get("/")
async def root():
    return Result.success()


def loop_factory() -> asyncio.AbstractEventLoop:
    """Initialize keyword search and open the database connection."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", reload=True, port=9090, loop="main:loop_factory")

@app.get("/health/ready")
async def readiness():
    from tortoise import connections
    from ai import vector_store
    from starlette.responses import JSONResponse
    try:
        await connections.get("default").execute_query("SELECT 1")
        connection = await vector_store._connect()
        await connection.close()
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
