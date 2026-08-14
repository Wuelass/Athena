"""Application service responsible for merging normalized game records.

Responsibilities:
- Combine records coming from several supported gaming platforms.
- Apply consistent duplicate-handling rules to normalized inputs.
- Preserve useful source information while producing one merged collection.
- Keep merge rules independent from collectors and presentation code.
Architecture notes:
- The service works on ``NormalizedGame`` objects rather than raw APIs.
- The same merge logic is reusable from CLI and graphical workflows.
- Centralizing the rule avoids divergent behaviour between interfaces.
- Platform-specific parsing is completed before this service is called.
- The service forms part of Athena's reusable business core.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.normalized_game import NormalizedGame


@dataclass
class MergeResult:
    merged_games: list[NormalizedGame] = field(default_factory=list)
    duplicates_removed: int = 0
    invalid_entries_skipped: int = 0

    def total_games(self) -> int:
        return len(self.merged_games)

    def to_dict(self) -> dict:
        return {
            "merged_games": [game.to_dict() for game in self.merged_games],
            "duplicates_removed": self.duplicates_removed,
            "invalid_entries_skipped": self.invalid_entries_skipped,
            "total_games": self.total_games(),
        }


class MergeService:
    def merge_game_lists(
        self,
        game_lists: list[list[NormalizedGame]],
        sort_by_playtime: bool = True,
    ) -> MergeResult:
        merged_games: list[NormalizedGame] = []
        duplicates_removed = 0
        invalid_entries_skipped = 0

        seen_keys = set()

        for games in game_lists:
            for game in games:
                if not self._is_valid_game(game):
                    invalid_entries_skipped += 1
                    continue

                unique_key = self._build_unique_key(game)

                if unique_key in seen_keys:
                    duplicates_removed += 1
                    continue

                seen_keys.add(unique_key)
                merged_games.append(game)

        if sort_by_playtime:
            merged_games.sort(key=lambda game: game.playtime_hours, reverse=True)

        return MergeResult(
            merged_games=merged_games,
            duplicates_removed=duplicates_removed,
            invalid_entries_skipped=invalid_entries_skipped,
        )

    def merge_reports(self, reports) -> MergeResult:
        game_lists = [report.games for report in reports]
        return self.merge_game_lists(game_lists)

    def _is_valid_game(self, game: NormalizedGame) -> bool:
        if not isinstance(game, NormalizedGame):
            return False

        if not game.name or not game.name.strip():
            return False

        if not game.platform or not game.platform.strip():
            return False

        return game.playtime_hours >= 0

    def _build_unique_key(self, game: NormalizedGame) -> tuple:
        return (
            game.platform.strip().lower(),
            (game.game_id or "").strip().lower(),
            game.name.strip().lower(),
        )