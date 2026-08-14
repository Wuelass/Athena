"""Repository dedicated to the Riot match cache.

Responsibilities:
- Read and write the cache used by Riot collectors.
- Centralize JSON persistence and file-path handling for cached matches.
- Expose account-level cache operations through explicit methods.
- Prevent collectors from depending directly on the storage format.
Architecture notes:
- ``LoLCollector`` consumes this repository through its public API.
- Persistence details remain isolated from Riot collection logic.
- A storage-format change is therefore concentrated in this component.
- The repository provides a clear data-access boundary in Athena.
- Cache reuse reduces repeated external API requests.
"""

import json
from pathlib import Path


class RiotMatchCacheRepository:
    def __init__(self, file_path: str = "data/riot_match_cache.json") -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.file_path.exists():
            return {}
        return json.loads(self.file_path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self.file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_account_cache(self, puuid: str) -> dict:
        data = self.load()
        return data.get(puuid, {"matches": {}})

    def save_account_cache(self, puuid: str, account_cache: dict) -> None:
        data = self.load()
        data[puuid] = account_cache
        self.save(data)