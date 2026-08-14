"""Domain model for an Athena user profile.

Responsibilities:
- Group profile-level information independently from platform collectors.
- Provide a stable structure for persistence and application services.
- Keep user metadata separate from individual normalized game records.
- Support serialization through a small predictable model contract.
Architecture notes:
- Repository code persists this model instead of UI-specific state.
- Business services can depend on the model without knowing storage details.
- The structure remains intentionally small and focused on profile data.
- Future profile attributes can be added without changing collectors.
- The model belongs to the domain layer of the Athena architecture.
"""

from dataclasses import dataclass, field

from models.platform_account import PlatformAccount


@dataclass
class UserProfile:
    profile_id: str
    display_name: str
    accounts: list[PlatformAccount] = field(default_factory=list)

    def add_account(self, account: PlatformAccount) -> None:
        self.accounts.append(account)

    def get_accounts_by_platform(self, platform: str) -> list[PlatformAccount]:
        return [
            account for account in self.accounts
            if account.platform == platform
        ]

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "accounts": [account.to_dict() for account in self.accounts],
        }