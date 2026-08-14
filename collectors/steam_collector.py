from __future__ import annotations

import json
import logging
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from collectors.base_collector import BaseCollector
from models.normalized_game import NormalizedGame
from models.platform_account import PlatformAccount
from models.sync_result import SyncResult

logger = logging.getLogger(__name__)


class SteamCollector(BaseCollector):
    platform_name = "steam"
    API_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"

    def __init__(self, api_key: str, timeout: int = 20) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout
        super().__init__()

        if not self.api_key:
            raise ValueError("api_key Steam ne peut pas être vide")

    def collect(self, account: PlatformAccount) -> tuple[list[NormalizedGame], SyncResult]:
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

    def _normalize_games(self, raw_games: list[dict]) -> list[NormalizedGame]:
        normalized_games: list[NormalizedGame] = []

        for index, raw_game in enumerate(raw_games):
            try:
                normalized_game = NormalizedGame.from_steam(raw_game)
                normalized_games.append(normalized_game)

            except (KeyError, TypeError, ValueError) as exc:
                game_name = raw_game.get("name", "Unknown Game") if isinstance(raw_game, dict) else "Invalid raw data"
                game_id = raw_game.get("appid", "Unknown appid") if isinstance(raw_game, dict) else "Unknown appid"

                logger.warning(
                    "Jeu Steam ignoré lors de la normalisation | index=%s | appid=%s | name=%s | error=%s",
                    index,
                    game_id,
                    game_name,
                    exc,
                )

                continue

        return normalized_games