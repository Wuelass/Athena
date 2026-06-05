from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from models.normalized_game import NormalizedGame


@dataclass
class GameStat:
    name: str
    platform: str
    playtime_hours: float

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "platform": self.platform,
            "playtime_hours": self.playtime_hours,
        }


@dataclass
class StatsSummary:
    total_games: int = 0
    total_playtime_hours: float = 0.0
    average_playtime_hours: float = 0.0
    estimated_games_count: int = 0
    top_games: List[GameStat] = field(default_factory=list)
    platform_breakdown: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_games": self.total_games,
            "total_playtime_hours": self.total_playtime_hours,
            "average_playtime_hours": self.average_playtime_hours,
            "estimated_games_count": self.estimated_games_count,
            "top_games": [game.to_dict() for game in self.top_games],
            "platform_breakdown": self.platform_breakdown,
        }


class StatsService:
    def build_summary(
        self,
        games: List[NormalizedGame],
        top_limit: int = 5,
    ) -> StatsSummary:
        if top_limit <= 0:
            raise ValueError("top_limit doit être supérieur à 0")

        total_games = len(games)
        total_playtime_hours = round(
            sum(game.playtime_hours for game in games),
            2,
        )

        average_playtime_hours = 0.0
        if total_games > 0:
            average_playtime_hours = round(total_playtime_hours / total_games, 2)

        estimated_games_count = sum(1 for game in games if game.is_estimated)

        top_games_sorted = sorted(
            games,
            key=lambda game: game.playtime_hours,
            reverse=True,
        )[:top_limit]

        top_games = [
            GameStat(
                name=game.name,
                platform=game.platform,
                playtime_hours=game.playtime_hours,
            )
            for game in top_games_sorted
        ]

        platform_breakdown = self._build_platform_breakdown(games)

        return StatsSummary(
            total_games=total_games,
            total_playtime_hours=total_playtime_hours,
            average_playtime_hours=average_playtime_hours,
            estimated_games_count=estimated_games_count,
            top_games=top_games,
            platform_breakdown=platform_breakdown,
        )

    def total_playtime(self, games: List[NormalizedGame]) -> float:
        return round(sum(game.playtime_hours for game in games), 2)

    def total_games(self, games: List[NormalizedGame]) -> int:
        return len(games)

    def top_games(
        self,
        games: List[NormalizedGame],
        limit: int = 5,
    ) -> List[GameStat]:
        if limit <= 0:
            raise ValueError("limit doit être supérieur à 0")

        sorted_games = sorted(
            games,
            key=lambda game: game.playtime_hours,
            reverse=True,
        )[:limit]

        return [
            GameStat(
                name=game.name,
                platform=game.platform,
                playtime_hours=game.playtime_hours,
            )
            for game in sorted_games
        ]

    def _build_platform_breakdown(self, games: List[NormalizedGame]) -> dict:
        breakdown: dict = {}

        for game in games:
            platform = game.platform

            if platform not in breakdown:
                breakdown[platform] = {
                    "game_count": 0,
                    "total_playtime_hours": 0.0,
                }

            breakdown[platform]["game_count"] += 1
            breakdown[platform]["total_playtime_hours"] += game.playtime_hours

        for platform_data in breakdown.values():
            platform_data["total_playtime_hours"] = round(
                platform_data["total_playtime_hours"],
                2,
            )

        return breakdown