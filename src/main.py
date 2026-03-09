import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from auth.router import users_router
from short_url.router import links_router
from short_url.utils import run_cleanup


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(run_cleanup())
    yield
    cleanup_task.cancel()

app = FastAPI(lifespan=lifespan)

app.include_router(users_router, prefix="/auth")
app.include_router(links_router, prefix="/links")
