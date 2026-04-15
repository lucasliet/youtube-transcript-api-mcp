from typing import List, Literal

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel

from ._api import YouTubeTranscriptApi
from ._errors import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    NotTranslatable,
    RequestBlocked,
    TranscriptsDisabled,
    TranslationLanguageNotAvailable,
    VideoUnavailable,
    YouTubeTranscriptApiException,
)
from .formatters import FormatterLoader

rest_router = APIRouter(prefix="/api", tags=["transcripts"])

_FORMATTER_LOADER = FormatterLoader()


class TranscriptSnippetResponse(BaseModel):
    text: str
    start: float
    duration: float


class FetchTranscriptResponse(BaseModel):
    video_id: str
    language: str
    language_code: str
    is_generated: bool
    snippets: List[TranscriptSnippetResponse]


class TranslationLanguageResponse(BaseModel):
    language: str
    language_code: str


class TranscriptMetadataResponse(BaseModel):
    video_id: str
    language: str
    language_code: str
    is_generated: bool
    is_translatable: bool
    translation_languages: List[TranslationLanguageResponse]


class ListTranscriptsResponse(BaseModel):
    video_id: str
    transcripts: List[TranscriptMetadataResponse]


class ErrorResponse(BaseModel):
    error: str
    type: str


def _error_response(exc: YouTubeTranscriptApiException, status_code: int):
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=str(exc), type=type(exc).__name__).model_dump(),
    )


def _map_exception(exc: YouTubeTranscriptApiException) -> JSONResponse:
    if isinstance(exc, InvalidVideoId):
        return _error_response(exc, 400)
    if isinstance(exc, NotTranslatable):
        return _error_response(exc, 400)
    if isinstance(exc, TranslationLanguageNotAvailable):
        return _error_response(exc, 400)
    if isinstance(exc, VideoUnavailable):
        return _error_response(exc, 404)
    if isinstance(exc, TranscriptsDisabled):
        return _error_response(exc, 404)
    if isinstance(exc, NoTranscriptFound):
        return _error_response(exc, 404)
    if isinstance(exc, AgeRestricted):
        return _error_response(exc, 403)
    if isinstance(exc, (RequestBlocked, IpBlocked)):
        return _error_response(exc, 403)
    if isinstance(exc, CouldNotRetrieveTranscript):
        return _error_response(exc, 500)
    return _error_response(exc, 500)


def _create_api() -> YouTubeTranscriptApi:
    from requests import Session

    _BROWSER_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    session = Session()
    session.headers.update({"User-Agent": _BROWSER_USER_AGENT})
    return YouTubeTranscriptApi(http_client=session)


@rest_router.get(
    "/videos/{video_id}/transcripts",
    response_model=ListTranscriptsResponse,
    responses={500: {"model": ErrorResponse}},
)
def list_transcripts(video_id: str):
    """
    Lists all available transcripts for a YouTube video.
    """
    try:
        api = _create_api()
        transcript_list = api.list(video_id)
    except YouTubeTranscriptApiException as exc:
        return _map_exception(exc)

    transcripts = []
    for transcript in transcript_list:
        transcripts.append(
            TranscriptMetadataResponse(
                video_id=transcript.video_id,
                language=transcript.language,
                language_code=transcript.language_code,
                is_generated=transcript.is_generated,
                is_translatable=transcript.is_translatable,
                translation_languages=[
                    TranslationLanguageResponse(
                        language=tl.language,
                        language_code=tl.language_code,
                    )
                    for tl in transcript.translation_languages
                ],
            )
        )

    return ListTranscriptsResponse(
        video_id=transcript_list.video_id,
        transcripts=transcripts,
    )


@rest_router.get(
    "/videos/{video_id}/transcript",
    response_model=FetchTranscriptResponse,
    responses={500: {"model": ErrorResponse}},
)
def fetch_transcript(
    video_id: str,
    languages: str = Query(
        "en", description="Comma-separated language codes in priority order"
    ),
    preserve_formatting: bool = Query(False, description="Keep HTML text formatting"),
):
    """
    Fetches the transcript for a YouTube video as structured JSON with snippets.
    """
    langs = [lang.strip() for lang in languages.split(",")]
    try:
        api = _create_api()
        transcript = api.fetch(
            video_id,
            languages=langs,
            preserve_formatting=preserve_formatting,
        )
    except YouTubeTranscriptApiException as exc:
        return _map_exception(exc)

    return FetchTranscriptResponse(
        video_id=transcript.video_id,
        language=transcript.language,
        language_code=transcript.language_code,
        is_generated=transcript.is_generated,
        snippets=[
            TranscriptSnippetResponse(
                text=snippet.text,
                start=snippet.start,
                duration=snippet.duration,
            )
            for snippet in transcript
        ],
    )


@rest_router.get(
    "/videos/{video_id}/transcript/translate",
    response_model=FetchTranscriptResponse,
    responses={500: {"model": ErrorResponse}},
)
def fetch_translated_transcript(
    video_id: str,
    target_language: str = Query(
        ..., description="Target language code for translation"
    ),
    source_languages: str = Query(
        "en", description="Comma-separated source language codes in priority order"
    ),
    preserve_formatting: bool = Query(False, description="Keep HTML text formatting"),
):
    """
    Fetches a translated transcript for a YouTube video.
    """
    source_langs = [lang.strip() for lang in source_languages.split(",")]
    try:
        api = _create_api()
        transcript_list = api.list(video_id)
        transcript = transcript_list.find_transcript(source_langs)
        translated = transcript.translate(target_language)
        fetched = translated.fetch(preserve_formatting=preserve_formatting)
    except YouTubeTranscriptApiException as exc:
        return _map_exception(exc)

    return FetchTranscriptResponse(
        video_id=fetched.video_id,
        language=fetched.language,
        language_code=fetched.language_code,
        is_generated=fetched.is_generated,
        snippets=[
            TranscriptSnippetResponse(
                text=snippet.text,
                start=snippet.start,
                duration=snippet.duration,
            )
            for snippet in fetched
        ],
    )


@rest_router.get(
    "/videos/{video_id}/transcript/formatted",
    responses={200: {"content": {"text/plain": {}}}},
)
def fetch_transcript_formatted(
    video_id: str,
    languages: str = Query(
        "en", description="Comma-separated language codes in priority order"
    ),
    format: Literal["text", "json", "srt", "webvtt"] = Query(
        "text", description="Output format"
    ),
):
    """
    Fetches and formats a transcript for a YouTube video.
    Supports: text, json, srt, webvtt.
    """
    langs = [lang.strip() for lang in languages.split(",")]
    try:
        api = _create_api()
        transcript = api.fetch(video_id, languages=langs)
    except YouTubeTranscriptApiException as exc:
        return _map_exception(exc)

    try:
        formatter = _FORMATTER_LOADER.load(format)
    except FormatterLoader.UnknownFormatterType as exc:
        return _error_response(exc, 400)

    formatted = formatter.format_transcript(transcript)

    if format == "json":
        return PlainTextResponse(content=formatted, media_type="application/json")

    return PlainTextResponse(content=formatted)
