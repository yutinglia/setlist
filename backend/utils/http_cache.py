"""HTTP cache controls for session-bearing and administrator responses."""

from fastapi import Response


def private_response_headers(
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return headers suitable for responses containing authentication state."""
    headers = {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Vary": "Cookie",
    }
    if extra is not None:
        headers.update(extra)
    return headers


def prevent_private_response_caching(response: Response) -> None:
    """Prevent private session data from being stored by browsers or proxies."""
    headers = private_response_headers()
    response.headers["Cache-Control"] = headers["Cache-Control"]
    response.headers["Pragma"] = headers["Pragma"]

    vary_values = {
        value.strip()
        for value in response.headers.get("Vary", "").split(",")
        if value.strip()
    }
    vary_values.add("Cookie")
    response.headers["Vary"] = ", ".join(sorted(vary_values, key=str.casefold))
