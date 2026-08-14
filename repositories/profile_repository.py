"""Persistence repository for Athena user profiles.

Responsibilities:
- Centralize reading and writing of profile information.
- Hide the concrete storage representation from application services.
- Convert persisted values to and from the user-profile domain model.
- Provide one persistence boundary for profile-related operations.
Architecture notes:
- Callers do not manipulate profile files directly.
- Storage changes remain localized to the repository implementation.
- File-system details are kept outside collectors and presentation classes.
- The repository supports separation between domain and persistence layers.
- Explicit methods make persistence operations easier to test and replace.
"""

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