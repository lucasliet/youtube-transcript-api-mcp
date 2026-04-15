from unittest import TestCase
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient


@patch("youtube_transcript_api._rest_routes._create_api")
@patch("youtube_transcript_api._mcp._create_api")
def _get_client(mock_mcp_api, mock_rest_api):
    from main import app

    mock_api = MagicMock()
    mock_mcp_api.return_value = mock_api
    mock_rest_api.return_value = mock_api

    return TestClient(app, raise_server_exceptions=False)


class TestMcpOptions(TestCase):
    def test_mcp_options_returns_204(self):
        client = _get_client()
        response = client.options("/mcp")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_mcp_options_with_path_returns_204(self):
        client = _get_client()
        response = client.options("/mcp/some/path")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")


class TestMcpHandler(TestCase):
    @patch("youtube_transcript_api._mcp_routes._mcp_asgi")
    def test_mcp_post_proxies_to_asgi(self, mock_asgi):
        received = []

        async def fake_asgi_handler(scope, receive, send):
            received.append(await receive())
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"result": "ok"}',
                }
            )

        mock_asgi.side_effect = fake_asgi_handler

        client = _get_client()
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        response = client.post("/mcp", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(response.json()["result"], "ok")
        self.assertTrue(received)
        self.assertIn(b"initialize", received[0]["body"])

    @patch("youtube_transcript_api._mcp_routes._mcp_asgi", new_callable=AsyncMock)
    def test_mcp_get_proxies_to_asgi(self, mock_asgi):
        async def fake_asgi_handler(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"ok",
                }
            )

        mock_asgi.side_effect = fake_asgi_handler

        client = _get_client()
        response = client.get("/mcp")

        self.assertEqual(response.status_code, 200)

    @patch("youtube_transcript_api._mcp_routes._mcp_asgi", new_callable=AsyncMock)
    def test_mcp_delete_proxies_to_asgi(self, mock_asgi):
        async def fake_asgi_handler(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"",
                }
            )

        mock_asgi.side_effect = fake_asgi_handler

        client = _get_client()
        response = client.delete("/mcp")

        self.assertEqual(response.status_code, 200)
