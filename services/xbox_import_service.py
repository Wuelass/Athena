from __future__ import annotations

import json
from pathlib import Path
from typing import List

from models.normalized_game import NormalizedGame


class XboxImportService:
    def __init__(self, json_path: str = "data/xbox/xbox_data.json") -> None:
        self.json_path = Path(json_path)

    def load_games(self) -> List[NormalizedGame]:
        if not self.json_path.exists():
            print(f"[Xbox] Fichier introuvable : {self.json_path}")
            return []

        with open(self.json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        games: List[NormalizedGame] = []

        for item in raw_data:
            game_name = str(item.get("game_name", "")).strip()
            playtime_hours = self._safe_float(item.get("playtime_hours", 0.0))

            if not game_name:
                continue

            games.append(
                NormalizedGame(
                    name=game_name,
                    platform="xbox",
                    playtime_hours=playtime_hours,
                )
            )

        print(f"[Xbox] {len(games)} jeux chargés depuis {self.json_path}")
        return games

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return 0.0