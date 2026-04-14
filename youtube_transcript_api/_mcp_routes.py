from fastapi import APIRouter, Request
from starlette.responses import Response

from ._mcp import mcp

mcp_router = APIRouter(tags=["mcp"])

_mcp_asgi = mcp.streamable_http_app()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "86400",
}


@mcp_router.options("/mcp")
@mcp_router.options("/mcp/{path:path}")
async def mcp_options(path: str = ""):
    return Response(status_code=204, headers=CORS_HEADERS)


@mcp_router.api_route("/mcp", methods=["GET", "POST", "DELETE"])
@mcp_router.api_route("/mcp/{path:path}", methods=["GET", "POST", "DELETE"])
async def mcp_handler(request: Request, path: str = ""):
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

    headers.update(CORS_HEADERS)

    return Response(content=resp_body, status_code=status_code, headers=headers)
