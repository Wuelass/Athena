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


class OsuCollector(BaseCollector):
    platform_name = "osu"

    TOKEN_URL = "https://osu.ppy.sh/oauth/token"
    USER_URL_TEMPLATE = "https://osu.ppy.sh/api/v2/users/{user_id}"

    def __init__(self, client_id: str, client_secret: str, timeout: int = 20) -> None:
        self.client_id = str(client_id).strip()
        self.client_secret = str(client_secret).strip()
        self.timeout = timeout
        super().__init__()

        if not self.client_id:
            raise ValueError("client_id osu ne peut pas être vide")

        if not self.client_secret:
            raise ValueError("client_secret osu ne peut pas être vide")

    def collect(self, account: PlatformAccount) -> Tuple[List[NormalizedGame], SyncResult]:
        self.validate_account(account)

        started_at = self.now_iso()
        start_timer = perf_counter()

        try:
            access_token = self._get_access_token()
            profile_data = self._fetch_user_profile(
                account_id=account.account_id,
                access_token=access_token,
            )

            playtime_hours, is_estimated, confidence = self._extract_playtime(profile_data)

            game = NormalizedGame.from_osu(
                playtime_hours=playtime_hours,
                raw_data=profile_data,
                username=account.username or account.display_name,
                is_estimated=is_estimated,
                confidence=confidence,
            )

            duration = perf_counter() - start_timer
            finished_at = self.now_iso()

            result = self.build_success_result(
                total_games_found=1,
                total_games_imported=1,
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                raw_summary={
                    "osu_account_id": account.account_id,
                    "username": account.username,
                    "playtime_hours": playtime_hours,
                    "is_estimated": is_estimated,
                },
            )

            return [game], result

        except Exception as exc:
            duration = perf_counter() - start_timer
            finished_at = self.now_iso()

            result = self.build_failure_result(
                error_message=str(exc),
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                raw_summary={
                    "osu_account_id": account.account_id,
                    "username": account.username,
                },
            )

            return [], result

    def _get_access_token(self) -> str:
        body = urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
                "scope": "public",
            }
        ).encode("utf-8")

        request = Request(
            self.TOKEN_URL,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "GameTimeTracker/1.0",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = self._read_http_error(exc)
            raise RuntimeError(f"osu token HTTP error {exc.code}: {details}") from exc
        except URLError as exc:
            raise RuntimeError(f"osu token URL error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("osu token timeout") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Réponse token osu invalide (JSON)") from exc

        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError("Aucun access_token reçu depuis osu")

        return access_token

    def _fetch_user_profile(self, account_id: str, access_token: str) -> dict:
        url = self.USER_URL_TEMPLATE.format(user_id=account_id)

        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "GameTimeTracker/1.0",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = self._read_http_error(exc)
            raise RuntimeError(f"osu profile HTTP error {exc.code}: {details}") from exc
        except URLError as exc:
            raise RuntimeError(f"osu profile URL error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("osu profile timeout") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Réponse profil osu invalide (JSON)") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Format inattendu reçu depuis osu API")

        return payload

    def _extract_playtime(self, profile_data: dict) -> tuple[float, bool, float]:
        statistics = profile_data.get("statistics") or {}
        play_time_seconds = statistics.get("play_time")

        if play_time_seconds is None:
            return 0.0, True, 0.2

        try:
            play_time_seconds = int(play_time_seconds)
        except (TypeError, ValueError):
            return 0.0, True, 0.1

        if play_time_seconds < 0:
            return 0.0, True, 0.1

        playtime_hours = round(play_time_seconds / 3600, 2)
        return playtime_hours, False, 1.0

    def _read_http_error(self, exc: HTTPError) -> str:
        try:
            raw = exc.read().decode("utf-8")
            if not raw:
                return "aucun détail"
            return raw
        except Exception:
            return "détail non lisible"