import os
from requests import Session

from ._api import YouTubeTranscriptApi
from .proxies import WebshareProxyConfig

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _create_api() -> YouTubeTranscriptApi:
    """Create a YouTubeTranscriptApi with a browser-like User-Agent and optional proxy."""
    session = Session()
    session.headers.update({"User-Agent": _BROWSER_USER_AGENT})

    proxy_username = os.environ.get("WEBSHARE_USERNAME")
    proxy_password = os.environ.get("WEBSHARE_PASSWORD")
    if proxy_username and proxy_password:
        proxy_config = WebshareProxyConfig(
            proxy_username=proxy_username,
            proxy_password=proxy_password,
        )
        return YouTubeTranscriptApi(
            http_client=session,
            proxy_config=proxy_config,
        )

    return YouTubeTranscriptApi(http_client=session)
