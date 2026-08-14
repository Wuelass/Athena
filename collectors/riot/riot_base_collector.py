"""Shared foundation for Riot platform collectors.

Responsibilities:
- Centralize behaviour common to Riot-based integrations.
- Provide reusable request and authentication helpers to subclasses.
- Keep shared Riot configuration in one implementation boundary.
- Reduce duplication between League of Legends and Valorant collectors.
Architecture notes:
- Specialized collectors extend this base instead of copying logic.
- Common integration rules therefore have a single maintenance point.
- Platform-specific behaviour remains implemented by each subclass.
- The class supports consistent error handling across Riot collectors.
- Reuse at this layer improves maintainability of external integrations.
"""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from collectors.base_collector import BaseCollector


class RiotBaseCollector(BaseCollector):
    def __init__(self, api_key: str, region: str, timeout: int = 20) -> None:
        self.api_key = api_key.strip()
        self.region = region.strip().lower()
        self.timeout = timeout
        super().__init__()

        if not self.api_key:
            raise ValueError("api_key Riot ne peut pas être vide")

        if not self.region:
            raise ValueError("region Riot ne peut pas être vide")

    def _headers(self) -> dict:
        return {
            "X-Riot-Token": self.api_key,
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        }

    def _get_json(self, url: str, max_retries: int = 5):
        attempt = 0

        while True:
            request = Request(url, headers=self._headers())

            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))

            except HTTPError as exc:
                if exc.code == 429:
                    retry_after = exc.headers.get("Retry-After")
                    wait_seconds = self._parse_retry_after(retry_after)

                    if attempt >= max_retries:
                        raise RuntimeError(
                            f"Riot API rate limit atteint après {max_retries} retries"
                        ) from exc

                    time.sleep(wait_seconds)
                    attempt += 1
                    continue

                try:
                    details = exc.read().decode("utf-8")
                except (OSError, UnicodeDecodeError):
                    details = "aucun détail"

                raise RuntimeError(
                    f"Riot API HTTP error {exc.code}: {details}"
                ) from exc

            except URLError as exc:
                raise RuntimeError(f"Riot API URL error: {exc.reason}") from exc

    def _parse_retry_after(self, retry_after: str | None) -> float:
        if retry_after is None:
            return 1.0

        try:
            value = float(retry_after)
        except (TypeError, ValueError):
            return 1.0

        if value <= 0:
            return 1.0

        return value + 0.1