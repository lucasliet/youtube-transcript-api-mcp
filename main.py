import contextlib
import json

from fastapi import FastAPI, Request
from starlette.responses import Response

from youtube_transcript_api._mcp import mcp


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="YouTube Transcript API - MCP Server", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


_mcp_asgi = mcp.streamable_http_app()


# CORS headers for browser clients
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "86400",
}


@app.options("/mcp")
@app.options("/mcp/{path:path}")
async def mcp_options(path: str = ""):
    """Handle CORS preflight requests explicitly."""
    return Response(status_code=204, headers=CORS_HEADERS)


@app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
@app.api_route("/mcp/{path:path}", methods=["GET", "POST", "DELETE"])
async def mcp_handler(request: Request, path: str = ""):
    """Forward requests to the MCP StreamableHTTP ASGI app."""
    scope = dict(request.scope)
    scope["path"] = "/" + path if path else "/"
    scope["root_path"] = ""

    body = await request.body()

    async def receive():
        return {"type": "http.request", "body": body}

    messages = []

    async def send(message):
        messages.append(message)

    await _mcp_asgi(scope, receive, send)

    status_code = 200
    headers = {}
    resp_body = b""
    for msg in messages:
        if msg["type"] == "http.response.start":
            status_code = msg["status"]
            for key, value in msg.get("headers", []):
                headers[key.decode()] = value.decode()
        elif msg["type"] == "http.response.body":
            resp_body += msg.get("body", b"")

    # Add CORS headers to response
    headers.update(CORS_HEADERS)

    return Response(content=resp_body, status_code=status_code, headers=headers)
