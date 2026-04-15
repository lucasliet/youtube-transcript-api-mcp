from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from youtube_transcript_api._mcp_routes import CORS_HEADERS


def _get_client():
    from main import app

    return TestClient(app)


class TestMcpOptions(TestCase):
    def test_mcp_options_returns_204_with_cors_headers(self):
        client = _get_client()
        response = client.options("/mcp")

        self.assertEqual(response.status_code, 204)
        for key, value in CORS_HEADERS.items():
            self.assertEqual(response.headers[key], value)

    def test_mcp_options_with_path_returns_204_with_cors_headers(self):
        client = _get_client()
        response = client.options("/mcp/some/path")

        self.assertEqual(response.status_code, 204)
        for key, value in CORS_HEADERS.items():
            self.assertEqual(response.headers[key], value)


class TestMcpHandler(TestCase):
    @patch("youtube_transcript_api._mcp_routes._mcp_asgi")
    def test_mcp_handler_post_request(self, mock_mcp_asgi):
        async def fake_asgi(scope, receive, send):
            received = await receive()
            self.assertEqual(received["type"], "http.request")
            self.assertIn(b"test", received["body"])
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": b'{"result": "ok"}'})

        mock_mcp_asgi.side_effect = fake_asgi

        client = _get_client()
        response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "test"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"result": "ok"})

        for key, value in CORS_HEADERS.items():
            self.assertEqual(response.headers[key], value)

    @patch("youtube_transcript_api._mcp_routes._mcp_asgi")
    def test_mcp_handler_get_request(self, mock_mcp_asgi):
        async def fake_asgi(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"hello"})

        mock_mcp_asgi.side_effect = fake_asgi

        client = _get_client()
        response = client.get("/mcp")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "hello")

    @patch("youtube_transcript_api._mcp_routes._mcp_asgi")
    def test_mcp_handler_delete_request(self, mock_mcp_asgi):
        async def fake_asgi(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"deleted"})

        mock_mcp_asgi.side_effect = fake_asgi

        client = _get_client()
        response = client.delete("/mcp")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "deleted")

    @patch("youtube_transcript_api._mcp_routes._mcp_asgi")
    def test_mcp_handler_with_path(self, mock_mcp_asgi):
        async def fake_asgi(scope, receive, send):
            self.assertEqual(scope["path"], "/stream")
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"streaming"})

        mock_mcp_asgi.side_effect = fake_asgi

        client = _get_client()
        response = client.post("/mcp/stream")

        self.assertEqual(response.status_code, 200)

    @patch("youtube_transcript_api._mcp_routes._mcp_asgi")
    def test_mcp_handler_non_200_status(self, mock_mcp_asgi):
        async def fake_asgi(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [(b"x-error", b"bad request")],
                }
            )
            await send({"type": "http.response.body", "body": b"bad request"})

        mock_mcp_asgi.side_effect = fake_asgi

        client = _get_client()
        response = client.post("/mcp", json={"invalid": True})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.text, "bad request")
        self.assertEqual(response.headers["x-error"], "bad request")
