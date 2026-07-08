from __future__ import annotations

from http import HTTPStatus
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


def handle_get(handler, parsed) -> bool:
    if parsed.path != "/api/image-proxy":
        return False

    query = parse_qs(parsed.query)
    source_url = (query.get("url") or [""])[0]
    parsed_source = urlparse(source_url)
    if parsed_source.scheme not in {"http", "https"} or not parsed_source.netloc:
        handler.send_error_json("Invalid image URL", HTTPStatus.BAD_REQUEST)
        return True

    request = Request(
        source_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            content_type = response.headers.get("Content-Type", "image/jpeg").split(";")[0]
            if not content_type.startswith("image/"):
                handler.send_error_json("URL did not return an image", HTTPStatus.BAD_GATEWAY)
                return True
            body = response.read(6_000_001)
    except Exception as exc:
        handler.send_error_json(f"Failed to load image: {exc}", HTTPStatus.BAD_GATEWAY)
        return True

    if len(body) > 6_000_000:
        handler.send_error_json("Image is too large", HTTPStatus.BAD_GATEWAY)
        return True

    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.end_headers()
    handler.wfile.write(body)
    return True
