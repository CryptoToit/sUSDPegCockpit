import httpx

DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
DEFAULT_HEADERS = {"User-Agent": "sUSDPegCockpit-pipeline/0.1 (+https://github.com/CryptoToit/sUSDPegCockpit)"}


def get_json(url: str, *, timeout: httpx.Timeout = DEFAULT_TIMEOUT) -> dict:
    """GET a URL and return parsed JSON. Raises on non-2xx or non-JSON responses."""
    with httpx.Client(timeout=timeout, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()
