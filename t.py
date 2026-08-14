import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import config

RIOT_API_KEY = config.RIOT_API_KEY
NAME = "R on CD"
TAG = "Dead"

encoded_name = quote(NAME)
encoded_tag = quote(TAG)

url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{encoded_name}/{encoded_tag}"

req = Request(
    url,
    headers={
        "X-Riot-Token": RIOT_API_KEY,
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
    }
)

try:
    with urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
        print(data)

except HTTPError as e:
    print("HTTP code:", e.code)
    try:
        print("Response body:", e.read().decode("utf-8"))
    except Exception:
        print("Impossible de lire le body.")
except URLError as e:
    print("URL error:", e.reason)