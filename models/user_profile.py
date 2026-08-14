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