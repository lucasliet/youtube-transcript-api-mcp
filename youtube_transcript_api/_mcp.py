from dataclasses import asdict
from typing import List, Optional

import json
from requests import Session

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from ._api import YouTubeTranscriptApi
from ._errors import YouTubeTranscriptApiException
from .formatters import FormatterLoader

mcp = FastMCP(
    "YouTube Transcript API",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_FORMATTER_LOADER = FormatterLoader()


def _create_api() -> YouTubeTranscriptApi:
    """Create a YouTubeTranscriptApi with a browser-like User-Agent."""
    session = Session()
    session.headers.update({"User-Agent": _BROWSER_USER_AGENT})
    return YouTubeTranscriptApi(http_client=session)


def _handle_error(exc: YouTubeTranscriptApiException) -> str:
    return str(exc)


@mcp.tool()
def fetch_transcript(
    video_id: str,
    languages: Optional[List[str]] = None,
    preserve_formatting: bool = False,
) -> str:
    """Fetches the transcript for a YouTube video.

    Returns the transcript snippets with text, start time, and duration,
    along with metadata (video_id, language, language_code, is_generated).

    Args:
        video_id: The YouTube video ID (NOT the full URL).
        languages: Language codes in descending priority (default: ["en"]).
        preserve_formatting: Whether to keep HTML text formatting.
    """
    if languages is None:
        languages = ["en"]

    try:
        api = _create_api()
        transcript = api.fetch(
            video_id,
            languages=languages,
            preserve_formatting=preserve_formatting,
        )
    except YouTubeTranscriptApiException as exc:
        return _handle_error(exc)

    return json.dumps(
        {
            "video_id": transcript.video_id,
            "language": transcript.language,
            "language_code": transcript.language_code,
            "is_generated": transcript.is_generated,
            "snippets": [asdict(snippet) for snippet in transcript],
        },
        indent=2,
    )


@mcp.tool()
def list_transcripts(video_id: str) -> str:
    """Lists all available transcripts for a YouTube video.

    Returns metadata for each transcript including language, language code,
    whether it's auto-generated, whether it's translatable, and available
    translation languages.

    Args:
        video_id: The YouTube video ID (NOT the full URL).
    """
    try:
        api = _create_api()
        transcript_list = api.list(video_id)
    except YouTubeTranscriptApiException as exc:
        return _handle_error(exc)

    transcripts = []
    for transcript in transcript_list:
        transcripts.append(
            {
                "video_id": transcript.video_id,
                "language": transcript.language,
                "language_code": transcript.language_code,
                "is_generated": transcript.is_generated,
                "is_translatable": transcript.is_translatable,
                "translation_languages": [
                    {
                        "language": tl.language,
                        "language_code": tl.language_code,
                    }
                    for tl in transcript.translation_languages
                ],
            }
        )

    return json.dumps(
        {
            "video_id": transcript_list.video_id,
            "transcripts": transcripts,
        },
        indent=2,
    )


@mcp.tool()
def fetch_transcript_formatted(
    video_id: str,
    languages: Optional[List[str]] = None,
    format: str = "text",
) -> str:
    """Fetches and formats a transcript for a YouTube video.

    Supports multiple output formats: text (plain text), json, srt, and webvtt.

    Args:
        video_id: The YouTube video ID (NOT the full URL).
        languages: Language codes in descending priority (default: ["en"]).
        format: Output format - one of: text, json, srt, webvtt (default: text).
    """
    if languages is None:
        languages = ["en"]

    try:
        api = _create_api()
        transcript = api.fetch(video_id, languages=languages)
    except YouTubeTranscriptApiException as exc:
        return _handle_error(exc)

    try:
        formatter = _FORMATTER_LOADER.load(format)
    except FormatterLoader.UnknownFormatterType as exc:
        return str(exc)

    return formatter.format_transcript(transcript)
