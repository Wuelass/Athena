from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from collectors.base_collector import BaseCollector
from models.normalized_game import NormalizedGame
from models.platform_account import PlatformAccount
from models.sync_result import SyncResult


@dataclass
class ImportReport:
    account: PlatformAccount
    games: list[NormalizedGame] = field(default_factory=list)
    sync_result: SyncResult | None = None

    def is_success(self) -> bool:
        return self.sync_result is not None and self.sync_result.success

    def total_games(self) -> int:
        return len(self.games)

    def to_dict(self) -> dict:
        return {
            "account": self.account.to_dict(),
            "games": [game.to_dict() for game in self.games],
            "sync_result": self.sync_result.to_dict() if self.sync_result else None,
        }


class ImportService:
    def __init__(self) -> None:
        pass

    def import_from_collector(
        self,
        collector: BaseCollector,
        account: PlatformAccount,
    ) -> ImportReport:
        games, sync_result = collector.collect(account)

        return ImportReport(
            account=account,
            games=games,
            sync_result=sync_result,
        )

    def import_many(
        self,
        collector_account_pairs: list[tuple[BaseCollector, PlatformAccount]],
    ) -> list[ImportReport]:
        reports: list[ImportReport] = []

        for collector, account in collector_account_pairs:
            report = self.import_from_collector(collector, account)
            reports.append(report)

        return reports

    def import_xbox_json(self, json_path: str = "data/xbox/xbox_data.json") -> list[NormalizedGame]:
        path = Path(json_path)

        if not path.exists():
            print(f"[Xbox] Fichier introuvable : {path}")
            return []

        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        games: list[NormalizedGame] = []

        for item in raw_data:
            game_name = str(item.get("game_name", "")).strip()
            if not game_name:
                continue

            try:
                game = NormalizedGame.from_xbox_json(item)
                games.append(game)
            except Exception as exc:
                print(f"[Xbox] Jeu ignoré ({game_name}) : {exc}")

        print(f"[Xbox] {len(games)} jeux chargés depuis {path}")
        return games