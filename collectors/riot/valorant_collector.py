from __future__ import annotations

import re
from time import perf_counter
from typing import Any
from urllib.parse import unquote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from collectors.riot.riot_base_collector import RiotBaseCollector
from models.normalized_game import NormalizedGame
from models.platform_account import PlatformAccount
from models.sync_result import SyncResult


class ValorantCollector(RiotBaseCollector):
    platform_name = "riot"

    def __init__(
        self,
        api_key: str,
        region: str,
        timeout: int = 30,
        debug: bool = False,
        headless: bool = True,
    ) -> None:
        super().__init__(api_key=api_key, region=region, timeout=timeout)
        self.debug = debug
        self.headless = headless

    def collect(self, account: PlatformAccount) -> tuple[list[NormalizedGame], SyncResult]:
        self.validate_account(account)

        started_at = self.now_iso()
        start_timer = perf_counter()

        try:
            tracker_url = self._extract_tracker_url(account)

            if self.debug:
                print("[VAL DEBUG] ===============================================")
                print("[VAL DEBUG] DÉBUT COLLECTE VALORANT")
                print(f"[VAL DEBUG] tracker_url={tracker_url}")
                print(f"[VAL DEBUG] timeout={self.timeout}")
                print(f"[VAL DEBUG] headless={self.headless}")
                print("[VAL DEBUG] ===============================================")

            scraped = self._scrape_tracker_profile(tracker_url)

            game = NormalizedGame(
                name="VALORANT",
                platform="riot",
                playtime_hours=scraped["hours_played"],
                launcher="riot",
                source="scraping",
                source_detail="tracker.gg profile page",
                is_estimated=True,
                confidence=0.7,
                raw_data={
                    "tracker_url": tracker_url,
                    "tracker_profile_name": scraped.get("profile_name"),
                    "hours_played": scraped["hours_played"],
                    "matches_played": scraped.get("matches_played"),
                    "wins": scraped.get("wins"),
                    "scrape_source": scraped.get("scrape_source"),
                    "text_excerpt": scraped.get("text_excerpt"),
                    "matched_pattern": scraped.get("matched_pattern"),
                },
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
                    "tracker_url": tracker_url,
                    "hours_played": scraped["hours_played"],
                    "matches_played": scraped.get("matches_played"),
                    "wins": scraped.get("wins"),
                    "scrape_source": scraped.get("scrape_source"),
                },
            )

            if self.debug:
                print(f"[VAL DEBUG] scrape_source={scraped.get('scrape_source')}")
                print(f"[VAL DEBUG] hours_played={scraped['hours_played']}")
                print(f"[VAL DEBUG] matches_played={scraped.get('matches_played')}")
                print(f"[VAL DEBUG] wins={scraped.get('wins')}")
                print("[VAL DEBUG] ===============================================")
                print("[VAL DEBUG] FIN COLLECTE VALORANT")
                print(f"[VAL DEBUG] durée totale={round(duration, 2)}s")
                print("[VAL DEBUG] ===============================================")

            return [game], result

        except Exception as exc:  # noqa: BLE001
            duration = perf_counter() - start_timer
            finished_at = self.now_iso()

            if self.debug:
                print("[VAL DEBUG] ===============================================")
                print("[VAL DEBUG] ECHEC COLLECTE VALORANT")
                print(f"[VAL DEBUG] erreur={exc}")
                print("[VAL DEBUG] ===============================================")

            result = self.build_failure_result(
                error_message=str(exc),
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                raw_summary={
                    "account_id": account.account_id,
                },
            )
            return [], result

    def _extract_tracker_url(self, account: PlatformAccount) -> str:
        raw_data = getattr(account, "raw_data", None) or {}

        candidates = [
            raw_data.get("tracker_url"),
            raw_data.get("valorant_tracker_url"),
            getattr(account, "profile_url", None),
        ]

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        game_name = raw_data.get("game_name")
        tag = raw_data.get("tag")

        if isinstance(game_name, str) and game_name.strip() and isinstance(tag, str) and tag.strip():
            encoded_name = self._encode_tracker_segment(game_name.strip())
            encoded_tag = self._encode_tracker_segment(tag.strip())

            return (
                "https://tracker.gg/valorant/profile/riot/"
                f"{encoded_name}%23{encoded_tag}/overview"
            )

        raise RuntimeError(
            "URL Tracker.gg introuvable. Ajoute raw_data['tracker_url'] "
            "ou bien game_name + tag dans le compte."
        )

    def _encode_tracker_segment(self, value: str) -> str:
        safe = value.strip().replace("#", "%23")
        safe = safe.replace(" ", "%20")
        return safe

    def _scrape_tracker_profile(self, url: str) -> dict:
        captured_json_payloads: list[dict[str, Any]] = []

        def on_response(response) -> None:
            try:
                resource_type = response.request.resource_type
                content_type = response.headers.get("content-type", "")
                response_url = response.url.lower()

                if resource_type not in ("xhr", "fetch"):
                    return

                if "json" not in content_type and not response_url.endswith(".json"):
                    return

                if "tracker.gg" not in response_url and "tracker.network" not in response_url:
                    return

                data = response.json()
                if isinstance(data, dict):
                    captured_json_payloads.append(
                        {
                            "url": response.url,
                            "data": data,
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                if self.debug:
                    print(f"[VAL DEBUG] réponse réseau JSON ignorée: {exc}")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.on("response", on_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                page.wait_for_timeout(3000)

                try:
                    page.wait_for_load_state("networkidle", timeout=12000)
                except PlaywrightTimeoutError:
                    if self.debug:
                        print("[VAL DEBUG] networkidle timeout ignoré")

                self._try_wait_for_stat_labels(page)

                # 1) Tentative texte visible
                text = page.locator("body").inner_text(timeout=5000)
                if self.debug:
                    excerpt = text[:2500].replace("\n", " | ")
                    print(f"[VAL DEBUG] text excerpt={excerpt}")

                parsed_from_text = self._parse_tracker_text(text)
                if parsed_from_text is not None:
                    parsed_from_text["text_excerpt"] = text[:2500]
                    parsed_from_text["profile_name"] = self._extract_profile_name_from_url(url)
                    parsed_from_text["scrape_source"] = "visible_text"
                    return parsed_from_text

                # 2) Tentative JSON réseau
                if self.debug:
                    print(f"[VAL DEBUG] json payloads capturés={len(captured_json_payloads)}")

                parsed_from_json = self._parse_tracker_json_payloads(captured_json_payloads)
                if parsed_from_json is not None:
                    parsed_from_json["text_excerpt"] = text[:2500]
                    parsed_from_json["profile_name"] = self._extract_profile_name_from_url(url)
                    parsed_from_json["scrape_source"] = "network_json"
                    return parsed_from_json

                # 3) Dump debug si rien trouvé
                html_excerpt = page.content()[:4000]
                if self.debug:
                    print(f"[VAL DEBUG] html excerpt={html_excerpt}")

                raise RuntimeError(
                    "Impossible de trouver les heures VALORANT sur Tracker.gg "
                    "(ni dans le texte visible ni dans les réponses JSON réseau)"
                )

            finally:
                browser.close()

    def _try_wait_for_stat_labels(self, page) -> None:
        label_patterns = [
            r"Hours Played",
            r"Time Played",
            r"Matches Played",
            r"Matches",
            r"Wins",
        ]

        for pattern in label_patterns:
            try:
                page.get_by_text(re.compile(pattern, re.IGNORECASE)).first.wait_for(timeout=2500)
                if self.debug:
                    print(f"[VAL DEBUG] label détecté: {pattern}")
                return
            except PlaywrightTimeoutError:
                continue

        if self.debug:
            print("[VAL DEBUG] aucun label de stat détecté directement")

    def _parse_tracker_text(self, text: str) -> dict | None:
        normalized = re.sub(r"[ \t]+", " ", text)
        normalized = normalized.replace("\r", "")

        hours_played, matched_pattern = self._extract_stat_number_with_pattern(
            normalized,
            [
                r"Hours Played\s*([0-9]+(?:[.,][0-9]+)?)",
                r"([0-9]+(?:[.,][0-9]+)?)\s*Hours Played",
                r"Time Played\s*([0-9]+(?:[.,][0-9]+)?)",
                r"([0-9]+(?:[.,][0-9]+)?)\s*Time Played",
                r"([0-9]+(?:[.,][0-9]+)?)\s*hrs",
                r"([0-9]+(?:[.,][0-9]+)?)\s*hours",
            ],
            float_mode=True,
        )

        if hours_played is None:
            return None

        matches_played, _ = self._extract_stat_number_with_pattern(
            normalized,
            [
                r"Matches Played\s*([0-9][0-9,\.]*)",
                r"Matches\s*([0-9][0-9,\.]*)",
                r"([0-9][0-9,\.]*)\s*Matches Played",
                r"([0-9][0-9,\.]*)\s*Matches",
            ],
            float_mode=False,
        )

        wins, _ = self._extract_stat_number_with_pattern(
            normalized,
            [
                r"Wins\s*([0-9][0-9,\.]*)",
                r"([0-9][0-9,\.]*)\s*Wins",
            ],
            float_mode=False,
        )

        return {
            "hours_played": hours_played,
            "matches_played": matches_played,
            "wins": wins,
            "matched_pattern": matched_pattern,
        }

    def _parse_tracker_json_payloads(self, payloads: list[dict[str, Any]]) -> dict | None:
        best_hours = None
        best_match = None

        for payload in payloads:
            data = payload.get("data")
            if not isinstance(data, dict):
                continue

            flat_pairs: list[tuple[str, Any]] = []
            self._flatten_json(data, flat_pairs)

            hours_played = self._find_numeric_by_key_keywords(
                flat_pairs,
                required_keywords=["hour"],
            )
            if hours_played is None:
                hours_played = self._find_numeric_by_key_keywords(
                    flat_pairs,
                    required_keywords=["time", "played"],
                )

            matches_played = self._find_numeric_by_key_keywords(
                flat_pairs,
                required_keywords=["match"],
            )
            wins = self._find_numeric_by_key_keywords(
                flat_pairs,
                required_keywords=["win"],
            )

            if hours_played is not None:
                best_hours = round(float(hours_played), 2)
                best_match = {
                    "hours_played": best_hours,
                    "matches_played": int(matches_played) if matches_played is not None else None,
                    "wins": int(wins) if wins is not None else None,
                    "matched_pattern": f"json:{payload.get('url')}",
                }
                break

        return best_match

    def _flatten_json(self, obj: Any, out: list[tuple[str, Any]], prefix: str = "") -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                next_prefix = f"{prefix}.{key}" if prefix else key
                out.append((next_prefix, value))
                self._flatten_json(value, out, next_prefix)
        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                next_prefix = f"{prefix}[{index}]"
                out.append((next_prefix, value))
                self._flatten_json(value, out, next_prefix)

    def _find_numeric_by_key_keywords(
        self,
        flat_pairs: list[tuple[str, Any]],
        required_keywords: list[str],
    ) -> float | None:
        for key, value in flat_pairs:
            lowered = key.lower()
            if not all(keyword in lowered for keyword in required_keywords):
                continue

            parsed = self._parse_unknown_number(value)
            if parsed is not None:
                return parsed

        return None

    def _extract_stat_number_with_pattern(
        self,
        text: str,
        patterns: list[str],
        float_mode: bool,
    ) -> tuple[float | int | None, str | None]:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue

            raw = match.group(1).strip()
            parsed = self._parse_number(raw, float_mode=float_mode)
            if parsed is not None:
                return parsed, pattern

        return None, None

    def _parse_unknown_number(self, value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            parsed = self._parse_number(value, float_mode=True)
            if isinstance(parsed, (int, float)):
                return float(parsed)

        return None

    def _parse_number(self, value: str, float_mode: bool) -> float | int | None:
        cleaned = value.strip().lower().replace(" ", "")

        if not cleaned:
            return None

        if cleaned.endswith("k"):
            try:
                base = float(cleaned[:-1].replace(",", "."))
                return round(base * 1000, 2) if float_mode else int(base * 1000)
            except ValueError:
                return None

        if cleaned.endswith("m"):
            try:
                base = float(cleaned[:-1].replace(",", "."))
                return round(base * 1_000_000, 2) if float_mode else int(base * 1_000_000)
            except ValueError:
                return None

        if float_mode:
            try:
                return round(float(cleaned.replace(",", ".")), 2)
            except ValueError:
                return None

        cleaned = cleaned.replace(",", "").replace(".", "")
        try:
            return int(cleaned)
        except ValueError:
            return None

    def _extract_profile_name_from_url(self, url: str) -> str | None:
        match = re.search(r"/profile/riot/([^/?]+)", url, flags=re.IGNORECASE)
        if not match:
            return None
        return unquote(match.group(1))