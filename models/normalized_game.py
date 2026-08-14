"""Canonical game model shared by Athena data sources.

Responsibilities:
- Represent a game using one structure regardless of its source platform.
- Validate core invariants such as non-negative playtime and confidence.
- Preserve optional source metadata required for later analysis.
- Provide constructors that translate platform records into one model.
Architecture notes:
- Steam, osu!, Riot and Xbox data converge on this domain object.
- Services can therefore operate without platform-specific conditionals.
- Factory class methods keep conversion rules close to the model contract.
- ``to_dict`` provides a stable serialization shape for output layers.
- The model is the main reusable boundary between collectors and services.
"""

from dataclasses import dataclass, field


@dataclass
class NormalizedGame:
    name: str
    platform: str
    playtime_hours: float

    game_id: str | None = None
    launcher: str | None = None
    genre: str | None = None
    last_played: str | None = None

    source: str = "api"
    source_detail: str | None = None

    is_estimated: bool = False
    confidence: float = 1.0

    icon_url: str | None = None
    cover_url: str | None = None

    raw_data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.platform = self.platform.strip().lower()
        self.playtime_hours = round(float(self.playtime_hours), 2)

        if self.playtime_hours < 0:
            raise ValueError("playtime_hours ne peut pas être négatif")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence doit être entre 0.0 et 1.0")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "platform": self.platform,
            "playtime_hours": self.playtime_hours,
            "game_id": self.game_id,
            "launcher": self.launcher,
            "genre": self.genre,
            "last_played": self.last_played,
            "source": self.source,
            "source_detail": self.source_detail,
            "is_estimated": self.is_estimated,
            "confidence": self.confidence,
            "icon_url": self.icon_url,
            "cover_url": self.cover_url,
            "raw_data": self.raw_data,
        }

    @classmethod
    def from_steam(cls, data: dict) -> "NormalizedGame":
        minutes = data.get("playtime_forever", 0)
        hours = round(minutes / 60, 2)

        return cls(
            name=data.get("name", "Unknown Game"),
            platform="steam",
            playtime_hours=hours,
            game_id=str(data.get("appid")) if data.get("appid") is not None else None,
            launcher="steam",
            source="api",
            source_detail="Steam GetOwnedGames",
            is_estimated=False,
            confidence=1.0,
            raw_data=data,
        )

    @classmethod
    def from_osu(
        cls,
        playtime_hours: float,
        raw_data: dict,
        username: str | None = None,
        is_estimated: bool = False,
        confidence: float = 1.0,
    ) -> "NormalizedGame":
        return cls(
            name="osu!",
            platform="osu",
            playtime_hours=playtime_hours,
            game_id=str(raw_data.get("id")) if raw_data.get("id") is not None else None,
            launcher="osu!",
            source="api",
            source_detail=f"osu profile: {username}" if username else "osu api",
            is_estimated=is_estimated,
            confidence=confidence,
            icon_url=raw_data.get("avatar_url"),
            raw_data=raw_data,
        )

    @classmethod
    def estimated_riot(cls, game_name: str, playtime_hours: float, raw_data: dict) -> "NormalizedGame":
        return cls(
            name=game_name,
            platform="riot",
            playtime_hours=playtime_hours,
            launcher="riot",
            source="api",
            source_detail="estimated from matches",
            is_estimated=True,
            confidence=0.6,
            raw_data=raw_data,
        )

    @classmethod
    def from_xbox_json(cls, data: dict) -> "NormalizedGame":
        return cls(
            name=data.get("game_name", "Unknown Game"),
            platform="xbox",
            playtime_hours=data.get("playtime_hours", 0.0),
            launcher="xbox",
            source="import",
            source_detail=data.get("source", "xbox_data.json"),
            is_estimated=False,
            confidence=0.8,
            raw_data=data,
        )