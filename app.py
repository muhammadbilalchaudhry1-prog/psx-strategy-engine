import json
import requests
from curl_cffi import requests as crequests


def fetch_full_psx_market():
    """Fetches full PSX summary by rotating through fallback proxies and endpoints."""
    # List of endpoints/proxies to bypass data-center IP blocks
    sources = [
        # Option 1: Direct PSX via curl_cffi Chrome impersonation
        (
            "direct",
            "https://dps.psx.com.pk/data/summary",
            {"impersonate": "chrome120"},
        ),
        # Option 2: Public AllOrigins CORS/Proxy Gateway
        (
            "proxy",
            "https://api.allorigins.win/get?url=https%3A%2F%2Fdps.psx.com.pk%2Fdata%2Fsummary",
            {},
        ),
        # Option 3: Alternative Corsproxy Gateway
        (
            "proxy_alt",
            "https://corsproxy.io/?url=https%3A%2F%2Fdps.psx.com.pk%2Fdata%2Fsummary",
            {},
        ),
    ]

    for mode, url, kwargs in sources:
        try:
            if mode == "direct":
                res = crequests.get(url, timeout=10, **kwargs)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and len(data) > 50:
                        return data
            else:
                # Standard fallback request via proxy wrappers
                res = requests.get(url, timeout=12)
                if res.status_code == 200:
                    payload = res.json()

                    # Handle AllOrigins structure: {"contents": "[{...}]"}
                    if "contents" in payload:
                        raw_contents = payload["contents"]
                        data = (
                            json.loads(raw_contents)
                            if isinstance(raw_contents, str)
                            else raw_contents
                        )
                    else:
                        data = payload

                    if isinstance(data, list) and len(data) > 50:
                        return data
        except Exception:
            continue

    return []
    
