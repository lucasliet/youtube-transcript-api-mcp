import json
from unittest import TestCase
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from youtube_transcript_api import (
    FetchedTranscript,
    FetchedTranscriptSnippet,
    TranscriptsDisabled,
    VideoUnavailable,
    InvalidVideoId,
    AgeRestricted,
    NoTranscriptFound,
    NotTranslatable,
    TranslationLanguageNotAvailable,
    IpBlocked,
    RequestBlocked,
    CouldNotRetrieveTranscript,
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


def _make_transcript_list(video_id="abc123"):
    mock_transcript = MagicMock()
    mock_transcript.video_id = video_id
    mock_transcript.language = "English"
    mock_transcript.language_code = "en"
    mock_transcript.is_generated = False
    mock_transcript.is_translatable = True
    mock_transcript.translation_languages = [
        MagicMock(language="Spanish", language_code="es"),
    ]

    mock_list = MagicMock()
    mock_list.__iter__ = MagicMock(return_value=iter([mock_transcript]))
    mock_list.video_id = video_id
    return mock_list


@patch("youtube_transcript_api._rest_routes._create_api")
def _get_client(mock_create_api=None):
    from main import app

    return TestClient(app)


class TestHealthEndpoint(TestCase):
    def test_health_returns_ok(self):
        client = _get_client()
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class TestCreateApiWithProxy(TestCase):
    @patch("youtube_transcript_api._factory.WebshareProxyConfig")
    @patch("youtube_transcript_api._factory.Session")
    @patch.dict(
        "os.environ", {"WEBSHARE_USERNAME": "testuser", "WEBSHARE_PASSWORD": "testpass"}
    )
    def test_creates_api_with_proxy_when_env_vars_set(
        self, mock_session_cls, mock_proxy_config_cls
    ):
        from youtube_transcript_api._factory import _create_api as create_factory_api
        from youtube_transcript_api._api import YouTubeTranscriptApi

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_proxy_config = MagicMock()
        mock_proxy_config_cls.return_value = mock_proxy_config

        api = create_factory_api()

        mock_proxy_config_cls.assert_called_once_with(
            proxy_username="testuser",
            proxy_password="testpass",
        )
        self.assertIsInstance(api, YouTubeTranscriptApi)

    @patch("youtube_transcript_api._factory.Session")
    @patch.dict("os.environ", {}, clear=True)
    def test_creates_api_without_proxy_when_env_vars_not_set(self, mock_session_cls):
        from youtube_transcript_api._factory import _create_api as create_factory_api
        from youtube_transcript_api._api import YouTubeTranscriptApi

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        api = create_factory_api()

        mock_session_cls.assert_called_once()
        self.assertIsInstance(api, YouTubeTranscriptApi)


class TestListTranscripts(TestCase):
    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_list_transcripts_success(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.list.return_value = _make_transcript_list()
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcripts")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["video_id"], "abc123")
        self.assertEqual(len(data["transcripts"]), 1)
        self.assertEqual(data["transcripts"][0]["language"], "English")
        self.assertEqual(data["transcripts"][0]["language_code"], "en")
        self.assertFalse(data["transcripts"][0]["is_generated"])
        self.assertTrue(data["transcripts"][0]["is_translatable"])
        self.assertEqual(
            data["transcripts"][0]["translation_languages"],
            [{"language": "Spanish", "language_code": "es"}],
        )

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_list_transcripts_disabled_returns_404(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.list.side_effect = TranscriptsDisabled("abc123")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcripts")

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["type"], "TranscriptsDisabled")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_list_transcripts_video_unavailable_returns_404(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.list.side_effect = VideoUnavailable("abc123")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcripts")

        self.assertEqual(response.status_code, 404)


class TestFetchTranscript(TestCase):
    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_transcript_success(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.return_value = _make_transcript()
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["video_id"], "abc123")
        self.assertEqual(data["language"], "English")
        self.assertEqual(data["language_code"], "en")
        self.assertFalse(data["is_generated"])
        self.assertEqual(len(data["snippets"]), 2)
        self.assertEqual(data["snippets"][0]["text"], "Hello")
        mock_api.fetch.assert_called_once_with(
            "abc123", languages=["en"], preserve_formatting=False
        )

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_transcript_custom_languages(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.return_value = _make_transcript()
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript?languages=de,en")

        self.assertEqual(response.status_code, 200)
        mock_api.fetch.assert_called_once_with(
            "abc123", languages=["de", "en"], preserve_formatting=False
        )

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_transcript_preserve_formatting(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.return_value = _make_transcript()
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript?preserve_formatting=true")

        self.assertEqual(response.status_code, 200)
        mock_api.fetch.assert_called_once_with(
            "abc123", languages=["en"], preserve_formatting=True
        )

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_transcript_invalid_video_id_returns_400(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = InvalidVideoId("invalid")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/invalid/transcript")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["type"], "InvalidVideoId")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_transcript_age_restricted_returns_403(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = AgeRestricted("abc123")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["type"], "AgeRestricted")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_transcript_no_transcript_found_returns_404(self, mock_create_api):
        mock_transcript_list = MagicMock()
        mock_transcript_list.__str__ = MagicMock(return_value="")

        mock_api = MagicMock()
        mock_api.fetch.side_effect = NoTranscriptFound(
            "abc123", ["en"], mock_transcript_list
        )
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["type"], "NoTranscriptFound")


class TestFetchTranslatedTranscript(TestCase):
    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_translated_success(self, mock_create_api):
        translated_transcript = _make_transcript()
        translated_transcript.language = "Spanish"
        translated_transcript.language_code = "es"

        mock_transcript = MagicMock()
        mock_transcript.translate.return_value.fetch.return_value = (
            translated_transcript
        )
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_transcript.return_value = mock_transcript

        mock_api = MagicMock()
        mock_api.list.return_value = mock_transcript_list
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get(
            "/api/videos/abc123/transcript/translate?target_language=es"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["language"], "Spanish")
        self.assertEqual(data["language_code"], "es")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_translated_with_source_languages(self, mock_create_api):
        translated_transcript = _make_transcript()

        mock_transcript = MagicMock()
        mock_transcript.translate.return_value.fetch.return_value = (
            translated_transcript
        )
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_transcript.return_value = mock_transcript

        mock_api = MagicMock()
        mock_api.list.return_value = mock_transcript_list
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get(
            "/api/videos/abc123/transcript/translate?target_language=es&source_languages=pt,en"
        )

        self.assertEqual(response.status_code, 200)
        mock_transcript_list.find_transcript.assert_called_once_with(["pt", "en"])

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_translated_error_returns_error_response(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.list.side_effect = TranscriptsDisabled("abc123")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get(
            "/api/videos/abc123/transcript/translate?target_language=es"
        )

        self.assertEqual(response.status_code, 404)


class TestFetchTranscriptFormatted(TestCase):
    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_formatted_text(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.return_value = _make_transcript()
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript/formatted?format=text")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Hello\nWorld")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_formatted_json(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.return_value = _make_transcript()
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript/formatted?format=json")

        self.assertEqual(response.status_code, 200)
        parsed = json.loads(response.text)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_formatted_srt(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.return_value = _make_transcript()
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript/formatted?format=srt")

        self.assertEqual(response.status_code, 200)
        self.assertIn("-->", response.text)
        self.assertIn("Hello", response.text)

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_formatted_webvtt(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.return_value = _make_transcript()
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript/formatted?format=webvtt")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.text.startswith("WEBVTT"))
        self.assertIn("Hello", response.text)

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_formatted_error_returns_error_response(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = TranscriptsDisabled("abc123")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript/formatted")

        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_fetch_formatted_custom_languages(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.return_value = _make_transcript()
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript/formatted?languages=de")

        self.assertEqual(response.status_code, 200)
        mock_api.fetch.assert_called_once_with("abc123", languages=["de"])


class TestExceptionMapping(TestCase):
    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_not_translatable_returns_400(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = NotTranslatable("abc123")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["type"], "NotTranslatable")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_translation_language_not_available_returns_400(self, mock_create_api):
        mock_transcript = MagicMock()
        mock_transcript.translate.side_effect = TranslationLanguageNotAvailable(
            "abc123"
        )
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_transcript.return_value = mock_transcript

        mock_api = MagicMock()
        mock_api.list.return_value = mock_transcript_list
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get(
            "/api/videos/abc123/transcript/translate?target_language=xyz"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["type"], "TranslationLanguageNotAvailable")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_ip_blocked_returns_403(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = IpBlocked("abc123")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["type"], "IpBlocked")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_request_blocked_returns_403(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = RequestBlocked("abc123")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["type"], "RequestBlocked")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_could_not_retrieve_transcript_returns_500(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = CouldNotRetrieveTranscript("abc123")
        mock_create_api.return_value = mock_api

        client = _get_client()
        response = client.get("/api/videos/abc123/transcript")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["type"], "CouldNotRetrieveTranscript")

    @patch("youtube_transcript_api._rest_routes._create_api")
    def test_unhandled_exception_returns_500(self, mock_create_api):
        mock_api = MagicMock()
        mock_api.fetch.side_effect = Exception("unexpected")
        mock_create_api.return_value = mock_api

        from main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/videos/abc123/transcript")

        self.assertEqual(response.status_code, 500)
