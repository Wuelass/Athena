import json
from pathlib import Path

from models.platform_account import PlatformAccount
from models.user_profile import UserProfile


class ProfileRepository:
    def __init__(self, file_path: str = "data/profiles.json") -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def save_profiles(self, profiles: list[UserProfile]) -> None:
        data = [profile.to_dict() for profile in profiles]
        self.file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_profiles(self) -> list[UserProfile]:
        if not self.file_path.exists():
            return []

        raw = json.loads(self.file_path.read_text(encoding="utf-8"))
        profiles: list[UserProfile] = []

        for item in raw:
            accounts = [
                PlatformAccount(**account_data)
                for account_data in item.get("accounts", [])
            ]

            profiles.append(
                UserProfile(
                    profile_id=item["profile_id"],
                    display_name=item["display_name"],
                    accounts=accounts,
                )
            )

        return profiles