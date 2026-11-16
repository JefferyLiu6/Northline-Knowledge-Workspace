"""Single-backend ownership, held by a dedicated MySQL connection."""
import asyncio
import hashlib
import logging
import os
from contextlib import asynccontextmanager, suppress
import aiomysql
from settings import TORTOISE_ORM

@asynccontextmanager
async def backend_lease():
    config = TORTOISE_ORM["connections"]["default"]["credentials"]
    connection = await aiomysql.connect(
        host=config["host"], port=config["port"], user=config["user"],
        password=config["password"], db=config["database"], autocommit=True,
        connect_timeout=10,
    )
    name = "rag-backend-" + hashlib.sha256(config["database"].encode()).hexdigest()[:40]
    monitor = None
    acquired = False
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT GET_LOCK(%s, 0)", (name,))
            acquired = (await cursor.fetchone())[0] == 1
        if not acquired:
            raise RuntimeError("Another backend owns this database. Run one backend worker; stop it before starting another.")
        async def heartbeat():
            while True:
                await asyncio.sleep(20)
                try:
                    async with connection.cursor() as cursor:
                        await cursor.execute("SELECT IS_USED_LOCK(%s) = CONNECTION_ID()", (name,))
                        if (await cursor.fetchone())[0] != 1:
                            raise RuntimeError("Backend ownership was lost")
                except Exception:
                    logging.exception("Database ownership lost; stopping before another backend can recover jobs")
                    # Fail closed: graceful shutdown could leave old background writers running.
                    os._exit(1)
        monitor = asyncio.create_task(heartbeat())
        yield
    finally:
        if monitor:
            monitor.cancel()
            with suppress(asyncio.CancelledError):
                await monitor
        if acquired:
            with suppress(Exception):
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT RELEASE_LOCK(%s)", (name,))
        connection.close()
