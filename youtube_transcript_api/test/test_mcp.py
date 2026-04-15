import json
from unittest import TestCase
from unittest.mock import patch, MagicMock

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    FetchedTranscript,
    FetchedTranscriptSnippet,
    TranscriptsDisabled,
)
from youtube_transcript_api._factory import _create_api, _BROWSER_USER_AGENT
from youtube_transcript_api._mcp import (
    fetch_transcript,
    list_transcripts,
    fetch_transcript_formatted,
    _handle_error,
)


def _make_transcript(video_id="abc123"):
    return FetchedTranscript(
        snippets=[
            FetchedTranscriptSnippet(text="Hello", start=0.0, duration=1.0),
            FetchedTranscriptSnippet(text="World", start=1.0, duration=2.0),
        ],
        language="English",
        language_code="en",
        is_generated=False,
        video_id=video_id,
    )


class TestCreateApi(TestCase):
    @patch("youtube_transcript_api._factory.Session")
    def test_session_has_browser_user_agent(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        _create_api()

        mock_session.headers.update.assert_called_once_with(
            {"User-Agent": _BROWSER_USER_AGENT}
        )

    def test_returns_youtube_transcript_api_instance(self):
        api = _create_api()
        self.assertIsInstance(api, YouTubeTranscriptApi)

    @patch("youtube_transcript_api._factory.WebshareProxyConfig")
    @patch("youtube_transcript_api._factory.Session")
    @patch.dict(
        "os.environ", {"WEBSHARE_USERNAME": "testuser", "WEBSHARE_PASSWORD": "testpass"}
    )
    def test_creates_api_with_proxy_when_env_vars_set(
        self, mock_session_cls, mock_proxy_config_cls
    ):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_proxy_config = MagicMock()
        mock_proxy_config_cls.return_value = mock_proxy_config

        api = _create_api()

        mock_proxy_config_cls.assert_called_once_with(
            proxy_username="testuser",
            proxy_password="testpass",
        )
        self.assertIsInstance(api, YouTubeTranscriptApi)


class TestHandleError(TestCase):
    def test_returns_string_representation(self):
        exc = TranscriptsDisabled("abc123")
        result = _handle_error(exc)
        self.assertIn("abc123", result)
        self.assertIsInstance(result, str)


class TestFetchTranscript(TestCase):
    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_transcript_success(self, mock_create_api):
        transcript = _make_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = transcript
        mock_create_api.return_value = mock_api

        result = fetch_transcript("abc123")
        parsed = json.loads(result)

        self.assertEqual(parsed["video_id"], "abc123")
        self.assertEqual(parsed["language"], "English")
        self.assertEqual(parsed["language_code"], "en")
        self.assertFalse(parsed["is_generated"])
        self.assertEqual(len(parsed["snippets"]), 2)
        self.assertEqual(parsed["snippets"][0]["text"], "Hello")
        mock_api.fetch.assert_called_once_with(
            "abc123", languages=["en"], preserve_formatting=False
        )

    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_transcript_custom_languages(self, mock_create_api):
        transcript = _make_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = transcript
        mock_create_api.return_value = mock_api

        result = fetch_transcript("abc123", languages=["de", "en"])
        parsed = json.loads(result)
        self.assertEqual(parsed["video_id"], "abc123")
        mock_api.fetch.assert_called_once_with(
            "abc123", languages=["de", "en"], preserve_formatting=False
        )

    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_transcript_preserve_formatting(self, mock_create_api):
        transcript = _make_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = transcript
        mock_create_api.return_value = mock_api

        fetch_transcript("abc123", preserve_formatting=True)
        mock_api.fetch.assert_called_once_with(
            "abc123", languages=["en"], preserve_formatting=True
        )

    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_transcript_error_returns_string(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = TranscriptsDisabled("abc123")
        mock_create_api.return_value = mock_api

        result = fetch_transcript("abc123")
        self.assertIn("abc123", result)
        self.assertIn("Subtitles are disabled", result)


class TestListTranscripts(TestCase):
    @patch("youtube_transcript_api._mcp._create_api")
    def test_list_transcripts_success(self, mock_create_api):
        mock_transcript = MagicMock()
        mock_transcript.video_id = "abc123"
        mock_transcript.language = "English"
        mock_transcript.language_code = "en"
        mock_transcript.is_generated = False
        mock_transcript.is_translatable = True
        mock_transcript.translation_languages = [
            MagicMock(language="Spanish", language_code="es"),
        ]
        mock_transcript_list = MagicMock()
        mock_transcript_list.__iter__ = MagicMock(return_value=iter([mock_transcript]))
        mock_transcript_list.video_id = "abc123"
        mock_api = MagicMock()
        mock_api.list.return_value = mock_transcript_list
        mock_create_api.return_value = mock_api

        result = list_transcripts("abc123")
        parsed = json.loads(result)

        self.assertEqual(parsed["video_id"], "abc123")
        self.assertEqual(len(parsed["transcripts"]), 1)
        self.assertEqual(parsed["transcripts"][0]["language"], "English")
        self.assertEqual(parsed["transcripts"][0]["language_code"], "en")
        self.assertTrue(parsed["transcripts"][0]["is_translatable"])
        self.assertEqual(
            parsed["transcripts"][0]["translation_languages"],
            [{"language": "Spanish", "language_code": "es"}],
        )

    @patch("youtube_transcript_api._mcp._create_api")
    def test_list_transcripts_error_returns_string(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.list.side_effect = TranscriptsDisabled("abc123")
        mock_create_api.return_value = mock_api

        result = list_transcripts("abc123")
        self.assertIn("abc123", result)
        self.assertIn("Subtitles are disabled", result)


class TestFetchTranscriptFormatted(TestCase):
    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_formatted_text(self, mock_create_api):
        transcript = _make_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = transcript
        mock_create_api.return_value = mock_api

        result = fetch_transcript_formatted("abc123")
        self.assertEqual(result, "Hello\nWorld")

    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_formatted_json(self, mock_create_api):
        transcript = _make_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = transcript
        mock_create_api.return_value = mock_api

        result = fetch_transcript_formatted("abc123", format="json")
        parsed = json.loads(result)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)

    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_formatted_srt(self, mock_create_api):
        transcript = _make_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = transcript
        mock_create_api.return_value = mock_api

        result = fetch_transcript_formatted("abc123", format="srt")
        self.assertIn("1", result)
        self.assertIn("-->", result)
        self.assertIn("Hello", result)

    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_formatted_webvtt(self, mock_create_api):
        transcript = _make_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = transcript
        mock_create_api.return_value = mock_api

        result = fetch_transcript_formatted("abc123", format="webvtt")
        self.assertTrue(result.startswith("WEBVTT"))
        self.assertIn("Hello", result)

    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_formatted_unknown_format(self, mock_create_api):
        transcript = _make_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = transcript
        mock_create_api.return_value = mock_api

        result = fetch_transcript_formatted("abc123", format="xml")
        self.assertIn("not supported", result)

    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_formatted_error_returns_string(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = TranscriptsDisabled("abc123")
        mock_create_api.return_value = mock_api

        result = fetch_transcript_formatted("abc123")
        self.assertIn("abc123", result)
        self.assertIn("Subtitles are disabled", result)

    @patch("youtube_transcript_api._mcp._create_api")
    def test_fetch_formatted_custom_languages(self, mock_create_api):
        transcript = _make_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = transcript
        mock_create_api.return_value = mock_api

        fetch_transcript_formatted("abc123", languages=["de"])
        mock_api.fetch.assert_called_once_with("abc123", languages=["de"])


class TestMcpLocalMain(TestCase):
    def test_main_calls_mcp_run(self):
        from youtube_transcript_api._mcp_local import mcp as mcp_instance

        with patch.object(mcp_instance, "run") as mock_run:
            from youtube_transcript_api._mcp_local import main

            main()
            mock_run.assert_called_once_with(transport="stdio")
