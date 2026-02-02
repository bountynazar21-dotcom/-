import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

pool: asyncpg.Pool | None = None


async def init_db():
    global pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
    )


async def fetch(query: str, *args):
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args):
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def execute(query: str, *args):
    async with pool.acquire() as conn:
        await conn.execute(query, *args)
