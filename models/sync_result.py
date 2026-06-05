from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SyncResult:
    success: bool
    platform: str

    total_games_found: int = 0
    total_games_imported: int = 0

    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    raw_summary: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.platform = self.platform.strip().lower()
        self.duration_seconds = round(float(self.duration_seconds), 2)

        if self.total_games_found < 0:
            raise ValueError("total_games_found ne peut pas être négatif")

        if self.total_games_imported < 0:
            raise ValueError("total_games_imported ne peut pas être négatif")

        if self.duration_seconds < 0:
            raise ValueError("duration_seconds ne peut pas être négatif")

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def add_error(self, message: str) -> None:
        message = message.strip()
        if message:
            self.errors.append(message)

    def add_warning(self, message: str) -> None:
        message = message.strip()
        if message:
            self.warnings.append(message)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "platform": self.platform,
            "total_games_found": self.total_games_found,
            "total_games_imported": self.total_games_imported,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "warnings": self.warnings,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "raw_summary": self.raw_summary,
        }

    @classmethod
    def success_result(
        cls,
        platform: str,
        total_games_found: int,
        total_games_imported: int,
        duration_seconds: float = 0.0,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        raw_summary: Optional[dict] = None,
    ) -> "SyncResult":
        return cls(
            success=True,
            platform=platform,
            total_games_found=total_games_found,
            total_games_imported=total_games_imported,
            duration_seconds=duration_seconds,
            started_at=started_at,
            finished_at=finished_at,
            raw_summary=raw_summary or {},
        )

    @classmethod
    def failure_result(
        cls,
        platform: str,
        error_message: str,
        duration_seconds: float = 0.0,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        raw_summary: Optional[dict] = None,
    ) -> "SyncResult":
        return cls(
            success=False,
            platform=platform,
            total_games_found=0,
            total_games_imported=0,
            duration_seconds=duration_seconds,
            errors=[error_message.strip()] if error_message.strip() else [],
            started_at=started_at,
            finished_at=finished_at,
            raw_summary=raw_summary or {},
        )