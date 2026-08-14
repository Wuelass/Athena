from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter

from collectors.base_collector import BaseCollector
from models.normalized_game import NormalizedGame
from models.platform_account import PlatformAccount
from models.sync_result import SyncResult


class EpicCollector(BaseCollector):
    platform_name = "epic"

    def __init__(
        self,
        saved_dir: str | None = None,
        debug: bool = False,
        enable_log_estimate: bool = True,
        max_session_hours: float = 8.0,
    ) -> None:
        super().__init__()
        self.saved_dir = Path(saved_dir).expanduser() if saved_dir else None
        self.debug = debug
        self.enable_log_estimate = enable_log_estimate
        self.max_session_hours = max_session_hours

        if self.max_session_hours <= 0:
            raise ValueError("max_session_hours doit être supérieur à 0")

    def collect(self, account: PlatformAccount) -> tuple[list[NormalizedGame], SyncResult]:
        self.validate_account(account)

        started_at = self.now_iso()
        start_timer = perf_counter()

        try:
            saved_dir = self._find_epic_saved_dir()
            installed_games = self._load_installed_games(saved_dir)

            if self.debug:
                print("[EPIC DEBUG] ===============================================")
                print("[EPIC DEBUG] DÉBUT COLLECTE EPIC")
                print(f"[EPIC DEBUG] saved_dir={saved_dir}")
                print(f"[EPIC DEBUG] enable_log_estimate={self.enable_log_estimate}")
                print(f"[EPIC DEBUG] max_session_hours={self.max_session_hours}")
                print(f"[EPIC DEBUG] installed_games={len(installed_games)}")

            session_summary: dict[str, dict] = {}
            if self.enable_log_estimate:
                session_summary = self._scan_logs_for_sessions(saved_dir)

            games = self._build_games(installed_games, session_summary)

            duration = perf_counter() - start_timer
            finished_at = self.now_iso()

            result = self.build_success_result(
                total_games_found=len(games),
                total_games_imported=len(games),
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                raw_summary={
                    "saved_dir": str(saved_dir),
                    "installed_games_count": len(installed_games),
                    "log_estimation_enabled": self.enable_log_estimate,
                    "session_summary_count": len(session_summary),
                },
            )

            if not games:
                result.add_warning("Aucun jeu Epic détecté localement")

            if self.enable_log_estimate and not session_summary:
                result.add_warning(
                    "Aucune session exploitable trouvée dans les logs Epic; "
                    "jeux installés importés avec 0 heure si aucun temps estimé"
                )

            if self.debug:
                print(f"[EPIC DEBUG] games_built={len(games)}")
                print("[EPIC DEBUG] ===============================================")
                print("[EPIC DEBUG] FIN COLLECTE EPIC")
                print(f"[EPIC DEBUG] durée totale={round(duration, 2)}s")
                print("[EPIC DEBUG] ===============================================")

            return games, result

        except Exception as exc:  # noqa: BLE001
            duration = perf_counter() - start_timer
            finished_at = self.now_iso()

            if self.debug:
                print("[EPIC DEBUG] ===============================================")
                print("[EPIC DEBUG] ECHEC COLLECTE EPIC")
                print(f"[EPIC DEBUG] erreur={exc}")
                print("[EPIC DEBUG] ===============================================")

            result = self.build_failure_result(
                error_message=str(exc),
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                raw_summary={
                    "saved_dir": str(self.saved_dir) if self.saved_dir else None,
                    "enable_log_estimate": self.enable_log_estimate,
                },
            )
            return [], result

    def _find_epic_saved_dir(self) -> Path:
        candidates: list[Path] = []

        if self.saved_dir:
            candidates.append(self.saved_dir)

        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "EpicGamesLauncher" / "Saved")

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate

        raise RuntimeError(
            "Dossier EpicGamesLauncher\\Saved introuvable. "
            "Configure EPIC_SAVED_DIR dans config.py si besoin."
        )

    def _load_installed_games(self, saved_dir: Path) -> dict[str, dict]:
        games: dict[str, dict] = {}

        # Source 1: launcher installed file
        launcher_installed_path = self._find_launcher_installed_path()
        if launcher_installed_path and launcher_installed_path.exists():
            if self.debug:
                print(f"[EPIC DEBUG] lecture LauncherInstalled.dat: {launcher_installed_path}")

            try:
                data = json.loads(launcher_installed_path.read_text(encoding="utf-8"))
                installations = data.get("InstallationList", [])
                if isinstance(installations, list):
                    for item in installations:
                        if not isinstance(item, dict):
                            continue

                        app_name = self._first_non_empty_str(
                            item.get("AppName"),
                            item.get("NamespaceId"),
                            item.get("ArtifactId"),
                            item.get("ItemId"),
                        )
                        display_name = self._first_non_empty_str(
                            item.get("AppName"),
                            item.get("ArtifactId"),
                            item.get("DisplayName"),
                        )

                        if not app_name:
                            continue

                        games.setdefault(app_name, {})
                        games[app_name].update(
                            {
                                "app_name": app_name,
                                "display_name": display_name or app_name,
                                "install_location": item.get("InstallLocation"),
                                "namespace_id": item.get("NamespaceId"),
                                "artifact_id": item.get("ArtifactId"),
                                "item_id": item.get("ItemId"),
                                "version": item.get("AppVersion"),
                                "source_files": [str(launcher_installed_path)],
                            }
                        )
            except (OSError, json.JSONDecodeError) as exc:
                if self.debug:
                    print(f"[EPIC DEBUG] échec lecture LauncherInstalled.dat: {exc}")

        # Source 2: manifest files
        manifest_dir = self._find_manifest_dir()
        if manifest_dir and manifest_dir.exists():
            if self.debug:
                print(f"[EPIC DEBUG] lecture manifests: {manifest_dir}")

            for manifest_path in manifest_dir.glob("*.item"):
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    if self.debug:
                        print(f"[EPIC DEBUG] échec lecture manifest {manifest_path.name}: {exc}")
                    continue

                app_name = self._first_non_empty_str(
                    data.get("AppName"),
                    data.get("LaunchExecutable"),
                    data.get("CatalogItemId"),
                    data.get("ArtifactId"),
                )
                display_name = self._first_non_empty_str(
                    data.get("DisplayName"),
                    data.get("AppName"),
                    data.get("ArtifactId"),
                )

                if not app_name:
                    continue

                entry = games.setdefault(app_name, {})
                source_files = entry.get("source_files", [])
                if str(manifest_path) not in source_files:
                    source_files.append(str(manifest_path))

                entry.update(
                    {
                        "app_name": app_name,
                        "display_name": display_name or app_name,
                        "install_location": data.get("InstallLocation") or entry.get("install_location"),
                        "namespace_id": data.get("NamespaceId") or entry.get("namespace_id"),
                        "artifact_id": data.get("ArtifactId") or entry.get("artifact_id"),
                        "item_id": data.get("CatalogItemId") or entry.get("item_id"),
                        "version": data.get("AppVersionString") or entry.get("version"),
                        "launch_executable": data.get("LaunchExecutable"),
                        "source_files": source_files,
                    }
                )

        if self.debug:
            for app_name, data in games.items():
                print(
                    f"[EPIC DEBUG] installed game: "
                    f"app_name={app_name}, "
                    f"display_name={data.get('display_name')}, "
                    f"install_location={data.get('install_location')}"
                )

        return games

    def _find_launcher_installed_path(self) -> Path | None:
        program_data = os.getenv("PROGRAMDATA")
        if not program_data:
            return None

        candidates = [
            Path(program_data) / "Epic" / "UnrealEngineLauncher" / "LauncherInstalled.dat",
            Path(program_data) / "Epic" / "EpicGamesLauncher" / "LauncherInstalled.dat",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def _find_manifest_dir(self) -> Path | None:
        program_data = os.getenv("PROGRAMDATA")
        if not program_data:
            return None

        candidates = [
            Path(program_data) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests",
            Path(program_data) / "Epic" / "UnrealEngineLauncher" / "Data" / "Manifests",
        ]

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate

        return None

    def _scan_logs_for_sessions(self, saved_dir: Path) -> dict[str, dict]:
        logs_dir = saved_dir / "Logs"
        if not logs_dir.exists() or not logs_dir.is_dir():
            if self.debug:
                print("[EPIC DEBUG] dossier Logs introuvable")
            return {}

        log_files = sorted(
            logs_dir.glob("*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=False,
        )

        if self.debug:
            print(f"[EPIC DEBUG] log_files={len(log_files)}")

        session_totals: dict[str, dict] = {}
        open_sessions: dict[str, datetime] = {}

        for log_path in log_files:
            try:
                text = log_path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                if self.debug:
                    print(f"[EPIC DEBUG] échec lecture log {log_path.name}: {exc}")
                continue

            for line in text.splitlines():
                timestamp = self._extract_log_timestamp(line)
                if timestamp is None:
                    continue

                launched_app = self._extract_launch_app_name(line)
                if launched_app:
                    open_sessions[launched_app] = timestamp
                    if self.debug:
                        print(
                            f"[EPIC DEBUG] launch détecté: "
                            f"app={launched_app}, ts={timestamp.isoformat()}"
                        )
                    continue

                stopped_app = self._extract_stop_app_name(line)
                if stopped_app:
                    started_at = open_sessions.pop(stopped_app, None)
                    if started_at is None:
                        continue

                    duration_seconds = (timestamp - started_at).total_seconds()
                    duration_seconds = max(0, int(duration_seconds))
                    max_seconds = int(self.max_session_hours * 3600)

                    if duration_seconds <= 60:
                        continue

                    duration_seconds = min(duration_seconds, max_seconds)

                    entry = session_totals.setdefault(
                        stopped_app,
                        {
                            "total_seconds": 0,
                            "session_count": 0,
                        },
                    )
                    entry["total_seconds"] += duration_seconds
                    entry["session_count"] += 1

                    if self.debug:
                        print(
                            f"[EPIC DEBUG] stop détecté: "
                            f"app={stopped_app}, durée={duration_seconds}s"
                        )

        if self.debug:
            for app_name, summary in session_totals.items():
                print(
                    f"[EPIC DEBUG] sessions summary: "
                    f"app={app_name}, "
                    f"total_seconds={summary['total_seconds']}, "
                    f"session_count={summary['session_count']}"
                )

        return session_totals

    def _extract_log_timestamp(self, line: str) -> datetime | None:
        # Format fréquent Unreal/Epic:
        # [2024.03.17-21.06.54:123][...]
        match = re.search(
            r"\[(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2})",
            line,
        )
        if not match:
            return None

        try:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second)  # noqa: DTZ001
        except ValueError:
            return None

    def _extract_launch_app_name(self, line: str) -> str | None:
        patterns = [
            r"Launching app[=: ]+([A-Za-z0-9_\-\.]+)",
            r"Launch app[=: ]+([A-Za-z0-9_\-\.]+)",
            r"AppName[=: ]+([A-Za-z0-9_\-\.]+).*Launching",
            r"Executing.*?([A-Za-z0-9_\-\.]+)\.exe",
        ]
        return self._extract_first_pattern(line, patterns)

    def _extract_stop_app_name(self, line: str) -> str | None:
        patterns = [
            r"App closed[=: ]+([A-Za-z0-9_\-\.]+)",
            r"Closing app[=: ]+([A-Za-z0-9_\-\.]+)",
            r"Closed app[=: ]+([A-Za-z0-9_\-\.]+)",
            r"Ending process.*?([A-Za-z0-9_\-\.]+)\.exe",
        ]
        return self._extract_first_pattern(line, patterns)

    def _extract_first_pattern(self, line: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value.lower().endswith(".exe"):
                    value = value[:-4]
                return value
        return None

    def _build_games(
        self,
        installed_games: dict[str, dict],
        session_summary: dict[str, dict],
    ) -> list[NormalizedGame]:
        games: list[NormalizedGame] = []

        for app_name, game_info in sorted(
            installed_games.items(),
            key=lambda item: (item[1].get("display_name") or item[0]).lower(),
        ):
            if not self._is_probable_game(app_name, game_info):
                if self.debug:
                    print(f"[EPIC DEBUG] entrée ignorée (non-jeu probable): {app_name}")
                continue
            matched_session = self._find_best_session_match(app_name, game_info, session_summary)

            total_seconds = 0
            session_count = 0
            source_detail = "epic launcher local install data"
            confidence = 0.5

            if matched_session:
                total_seconds = matched_session.get("total_seconds", 0)
                session_count = matched_session.get("session_count", 0)
                source_detail = "epic launcher local install data + log session estimate"
                confidence = 0.7

            playtime_hours = round(total_seconds / 3600, 2)

            game = NormalizedGame(
                name=game_info.get("display_name") or app_name,
                platform="epic",
                playtime_hours=playtime_hours,
                launcher="epic",
                source="local",
                source_detail=source_detail,
                is_estimated=True,
                confidence=confidence,
                raw_data={
                    "app_name": app_name,
                    "display_name": game_info.get("display_name"),
                    "install_location": game_info.get("install_location"),
                    "namespace_id": game_info.get("namespace_id"),
                    "artifact_id": game_info.get("artifact_id"),
                    "item_id": game_info.get("item_id"),
                    "version": game_info.get("version"),
                    "launch_executable": game_info.get("launch_executable"),
                    "source_files": game_info.get("source_files", []),
                    "session_count": session_count,
                    "total_seconds": total_seconds,
                },
            )
            games.append(game)

        return games

    def _find_best_session_match(
        self,
        app_name: str,
        game_info: dict,
        session_summary: dict[str, dict],
    ) -> dict | None:
        candidates = [
            app_name,
            game_info.get("artifact_id"),
            game_info.get("display_name"),
            game_info.get("launch_executable"),
        ]

        normalized_session_map = {
            self._normalize_key(key): value
            for key, value in session_summary.items()
        }

        for candidate in candidates:
            if not isinstance(candidate, str) or not candidate.strip():
                continue

            normalized = self._normalize_key(candidate)
            if normalized in normalized_session_map:
                return normalized_session_map[normalized]

        return None

    def _normalize_key(self, value: str) -> str:
        value = value.lower().strip()
        value = value.replace(".exe", "")
        value = re.sub(r"[^a-z0-9]+", "", value)
        return value

    def _first_non_empty_str(self, *values) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    
    def _is_probable_game(self, app_name: str, game_info: dict) -> bool:
        candidates = [
            app_name,
            game_info.get("display_name"),
            game_info.get("artifact_id"),
            game_info.get("install_location"),
        ]

        text = " ".join(
            str(value) for value in candidates
            if isinstance(value, str) and value.strip()
        ).lower()

        blocked_patterns = [
            "fabplugin",
            "unreal",
            "ue_",
            "ue5",
            "ue4",
            "engine",
            "plugin",
            "modding",
            "sample",
            "template",
        ]

        return not any(pattern in text for pattern in blocked_patterns)