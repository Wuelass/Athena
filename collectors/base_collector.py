from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Tuple

from models.normalized_game import NormalizedGame
from models.platform_account import PlatformAccount
from models.sync_result import SyncResult


class BaseCollector(ABC):
    platform_name: str = "unknown"

    def __init__(self) -> None:
        if not self.platform_name or self.platform_name == "unknown":
            raise ValueError("Chaque collector doit définir platform_name")

    @abstractmethod
    def collect(self, account: PlatformAccount) -> Tuple[List[NormalizedGame], SyncResult]:
        """
        Récupère les données d'une plateforme pour un compte donné.

        Retourne :
        - une liste de NormalizedGame
        - un SyncResult décrivant le résultat de la synchronisation
        """
        raise NotImplementedError

    def supports_account(self, account: PlatformAccount) -> bool:
        """
        Vérifie si ce collector peut traiter ce compte.
        """
        return account.platform == self.platform_name

    def validate_account(self, account: PlatformAccount) -> None:
        """
        Vérifie que le compte correspond bien à la plateforme du collector.
        """
        if not isinstance(account, PlatformAccount):
            raise TypeError("account doit être une instance de PlatformAccount")

        if not self.supports_account(account):
            raise ValueError(
                f"Compte incompatible : attendu '{self.platform_name}', reçu '{account.platform}'"
            )

        if not account.account_id:
            raise ValueError("Le compte fourni ne contient pas de account_id valide")

    def now_iso(self) -> str:
        """
        Retourne la date/heure courante au format ISO.
        """
        return datetime.now().isoformat(timespec="seconds")

    def build_success_result(
        self,
        total_games_found: int,
        total_games_imported: int,
        duration_seconds: float = 0.0,
        started_at: str | None = None,
        finished_at: str | None = None,
        raw_summary: dict | None = None,
    ) -> SyncResult:
        return SyncResult.success_result(
            platform=self.platform_name,
            total_games_found=total_games_found,
            total_games_imported=total_games_imported,
            duration_seconds=duration_seconds,
            started_at=started_at,
            finished_at=finished_at,
            raw_summary=raw_summary or {},
        )

    def build_failure_result(
        self,
        error_message: str,
        duration_seconds: float = 0.0,
        started_at: str | None = None,
        finished_at: str | None = None,
        raw_summary: dict | None = None,
    ) -> SyncResult:
        return SyncResult.failure_result(
            platform=self.platform_name,
            error_message=error_message,
            duration_seconds=duration_seconds,
            started_at=started_at,
            finished_at=finished_at,
            raw_summary=raw_summary or {},
        )