from __future__ import annotations

from time import perf_counter
from typing import List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from collectors.base_collector import BaseCollector
from models.normalized_game import NormalizedGame
from models.platform_account import PlatformAccount
from models.sync_result import SyncResult


class SteamCollector(BaseCollector):
    platform_name = "steam"
    API_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"

    def __init__(self, api_key: str, timeout: int = 20) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout
        super().__init__()

        if not self.api_key:
            raise ValueError("api_key Steam ne peut pas être vide")

    def collect(self, account: PlatformAccount) -> Tuple[List[NormalizedGame], SyncResult]:
        self.validate_account(account)

        started_at = self.now_iso()
        start_timer = perf_counter()

        try:
            raw_games = self._fetch_owned_games(account.account_id)
            games = self._normalize_games(raw_games)

            duration = perf_counter() - start_timer
            finished_at = self.now_iso()

            result = self.build_success_result(
                total_games_found=len(raw_games),
                total_games_imported=len(games),
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                raw_summary={
                    "steam_id": account.account_id,
                    "game_count": len(raw_games),
                },
            )

            return games, result

        except Exception as exc:
            duration = perf_counter() - start_timer
            finished_at = self.now_iso()

            result = self.build_failure_result(
                error_message=str(exc),
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                raw_summary={
                    "steam_id": account.account_id,
                },
            )

            return [], result

    def _fetch_owned_games(self, steam_id: str) -> list[dict]:
        params = {
            "key": self.api_key,
            "steamid": steam_id,
            "include_appinfo": "true",
            "include_played_free_games": "true",
            "format": "json",
        }

        url = f"{self.API_URL}?{urlencode(params)}"
        request = Request(
            url,
            headers={"User-Agent": "GameTimeTracker/1.0"},
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Steam API HTTP error: {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Steam API URL error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("Steam API timeout") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Réponse Steam invalide (JSON)") from exc

        response_data = payload.get("response", {})
        games = response_data.get("games", [])

        if not isinstance(games, list):
            raise RuntimeError("Format inattendu reçu depuis Steam API")

        return games

    def _normalize_games(self, raw_games: list[dict]) -> List[NormalizedGame]:
        normalized_games: List[NormalizedGame] = []

        for raw_game in raw_games:
            try:
                normalized_game = NormalizedGame.from_steam(raw_game)
                normalized_games.append(normalized_game)
            except Exception:
                # En V1, on ignore silencieusement les entrées invalides.
                # Plus tard, on pourra logger ça proprement.
                continue

        return normalized_games