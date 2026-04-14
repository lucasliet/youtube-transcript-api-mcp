import contextlib

from fastapi import FastAPI

from youtube_transcript_api._mcp import mcp
from youtube_transcript_api._mcp_routes import mcp_router
from youtube_transcript_api._rest_routes import rest_router


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="YouTube Transcript API", lifespan=lifespan)

app.include_router(mcp_router)
app.include_router(rest_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
