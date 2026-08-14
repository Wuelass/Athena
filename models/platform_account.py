"""Domain model describing an external gaming account.

Responsibilities:
- Store the identity and platform information needed for collection.
- Provide platform-specific constructors behind one account abstraction.
- Normalize identifiers before they are consumed by collectors or services.
- Keep account metadata separate from individual game records.
Architecture notes:
- Collectors receive a domain object instead of unrelated loose parameters.
- Factory methods centralize conversion from platform account formats.
- The model avoids duplicating account-shaping logic across workflows.
- Optional fields support platforms with different identity requirements.
- This object participates in the common normalized Athena data model.
"""

from dataclasses import dataclass, field


@dataclass
class PlatformAccount:
    platform: str
    account_id: str

    username: str | None = None
    display_name: str | None = None
    region: str | None = None
    tag: str | None = None

    is_active: bool = True
    is_connected: bool = False

    profile_url: str | None = None
    avatar_url: str | None = None

    metadata: dict = field(default_factory=dict)
    raw_data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.platform = self.platform.strip().lower()
        self.account_id = self.account_id.strip()

        if self.username is not None:
            self.username = self.username.strip()

        if self.display_name is not None:
            self.display_name = self.display_name.strip()

        if self.region is not None:
            self.region = self.region.strip().lower()

        if self.tag is not None:
            self.tag = self.tag.strip()

        if not isinstance(self.metadata, dict):
            self.metadata = {}

        if not isinstance(self.raw_data, dict):
            self.raw_data = {}

        if not self.platform:
            raise ValueError("platform ne peut pas être vide")

        if not self.account_id:
            raise ValueError("account_id ne peut pas être vide")

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "account_id": self.account_id,
            "username": self.username,
            "display_name": self.display_name,
            "region": self.region,
            "tag": self.tag,
            "is_active": self.is_active,
            "is_connected": self.is_connected,
            "profile_url": self.profile_url,
            "avatar_url": self.avatar_url,
            "metadata": self.metadata,
            "raw_data": self.raw_data,
        }

    @classmethod
    def from_steam(
        cls,
        steam_id: str,
        username: str | None = None,
        raw_data: dict | None = None,
    ) -> "PlatformAccount":
        return cls(
            platform="steam",
            account_id=steam_id,
            username=username,
            display_name=username,
            is_active=True,
            is_connected=True,
            raw_data=raw_data or {},
        )

    @classmethod
    def from_osu(
        cls,
        user_id: str,
        username: str | None = None,
        raw_data: dict | None = None,
    ) -> "PlatformAccount":
        return cls(
            platform="osu",
            account_id=user_id,
            username=username,
            display_name=username,
            is_active=True,
            is_connected=True,
            raw_data=raw_data or {},
        )

    @classmethod
    def from_riot(
        cls,
        puuid: str,
        game_name: str | None = None,
        tag: str | None = None,
        username: str | None = None,
        region: str | None = None,
        raw_data: dict | None = None,
    ) -> "PlatformAccount":

        if username and not game_name:
            if "#" in username:
                game_name, tag = username.split("#", 1)
            else:
                game_name = username

        display_name = None
        if game_name and tag:
            display_name = f"{game_name}#{tag}"
        elif game_name:
            display_name = game_name

        merged_raw_data = dict(raw_data or {})
        if game_name:
            merged_raw_data.setdefault("game_name", game_name)
        if tag:
            merged_raw_data.setdefault("tag", tag)

        return cls(
            platform="riot",
            account_id=puuid,
            username=game_name,
            display_name=display_name,
            region=region,
            tag=tag,
            is_active=True,
            is_connected=True,
            raw_data=merged_raw_data,
        )