"""League of Legends collector for Riot data.

Responsibilities:
- Retrieve match and account information required by Athena.
- Estimate playtime from the available Riot match history.
- Reuse the Riot cache repository instead of handling JSON directly.
- Keep Riot-specific pagination and request rules inside this layer.
Architecture notes:
- Persistent cache access is delegated to a repository object.
- External API details do not leak into services or UI classes.
- Collected values are prepared for normalized domain models.
- Caching reduces unnecessary requests to the external API.
- Errors are handled close to the external integration boundary.
"""

from __future__ import annotations

from time import perf_counter

from collectors.riot.riot_base_collector import RiotBaseCollector
from models.normalized_game import NormalizedGame
from models.platform_account import PlatformAccount
from models.sync_result import SyncResult
from repositories.riot_match_cache_repository import RiotMatchCacheRepository


class LoLCollector(RiotBaseCollector):
    platform_name = "riot"

    def __init__(
        self,
        api_key: str,
        region: str,
        platform_region: str,
        timeout: int = 20,
        max_matches: int = 200,
        batch_size: int = 100,
        debug: bool = False,
        use_mastery_estimate: bool = False,
        mastery_points_per_estimated_game: int = 1000,
        cache_repository: RiotMatchCacheRepository | None = None,
    ) -> None:
        super().__init__(api_key=api_key, region=region, timeout=timeout)

        self.platform_region = platform_region.strip().lower()
        self.max_matches = max_matches
        self.batch_size = batch_size
        self.debug = debug
        self.use_mastery_estimate = use_mastery_estimate
        self.mastery_points_per_estimated_game = mastery_points_per_estimated_game
        self.cache_repository = cache_repository or RiotMatchCacheRepository()

        if not self.platform_region:
            raise ValueError("platform_region Riot ne peut pas être vide")

        if self.max_matches <= 0:
            raise ValueError("max_matches doit être supérieur à 0")

        if self.batch_size <= 0:
            raise ValueError("batch_size doit être supérieur à 0")

        if self.batch_size > 100:
            raise ValueError("batch_size ne peut pas dépasser 100")

        if self.mastery_points_per_estimated_game <= 0:
            raise ValueError(
                "mastery_points_per_estimated_game doit être supérieur à 0"
            )

    def collect(self, account: PlatformAccount) -> tuple[list[NormalizedGame], SyncResult]:
        self.validate_account(account)

        started_at = self.now_iso()
        start_timer = perf_counter()

        try:
            puuid = account.account_id

            if self.debug:
                print("[LOL DEBUG] ===============================================")
                print("[LOL DEBUG] DÉBUT COLLECTE LOL")
                print(f"[LOL DEBUG] puuid={puuid}")
                print(f"[LOL DEBUG] region match-v5={self.region}")
                print(f"[LOL DEBUG] platform_region={self.platform_region}")
                print(f"[LOL DEBUG] timeout={self.timeout}")
                print(f"[LOL DEBUG] max_matches={self.max_matches}")
                print(f"[LOL DEBUG] batch_size={self.batch_size}")
                print(f"[LOL DEBUG] use_mastery_estimate={self.use_mastery_estimate}")
                print(
                    "[LOL DEBUG] mastery_points_per_estimated_game="
                    f"{self.mastery_points_per_estimated_game}"
                )
                print("[LOL DEBUG] ===============================================")

            match_ids = self._fetch_all_match_ids(
                puuid=puuid,
                batch_size=self.batch_size,
                max_matches=self.max_matches,
            )

            unique_match_ids = list(dict.fromkeys(match_ids))
            duplicate_count = len(match_ids) - len(unique_match_ids)

            if self.debug:
                print(f"[LOL DEBUG] total ids récupérés (brut) = {len(match_ids)}")
                print(f"[LOL DEBUG] total ids uniques = {len(unique_match_ids)}")
                print(f"[LOL DEBUG] doublons détectés = {duplicate_count}")

                if unique_match_ids:
                    print(f"[LOL DEBUG] premier match id = {unique_match_ids[0]}")
                    print(f"[LOL DEBUG] dernier match id = {unique_match_ids[-1]}")

            match_ids = unique_match_ids

            account_cache = self.cache_repository.get_account_cache(puuid)
            cached_matches = account_cache.get("matches", {})

            if not isinstance(cached_matches, dict):
                cached_matches = {}

            new_match_ids = [
                match_id for match_id in match_ids
                if match_id not in cached_matches
            ]

            if self.debug:
                print(f"[LOL DEBUG] déjà en cache = {len(cached_matches)}")
                print(f"[LOL DEBUG] nouveaux matchs = {len(new_match_ids)}")

                preview_count = min(10, len(new_match_ids))
                if preview_count > 0:
                    print(f"[LOL DEBUG] aperçu nouveaux matchs ({preview_count}) :")
                    for match_id in new_match_ids[:preview_count]:
                        print(f"[LOL DEBUG]   - {match_id}")

            added_count, skipped_count = self._fetch_and_store_new_match_data(
                new_match_ids=new_match_ids,
                cached_matches=cached_matches,
            )

            account_cache["matches"] = cached_matches
            self.cache_repository.save_account_cache(puuid, account_cache)

            total_seconds_observed = self._sum_cached_durations(cached_matches, match_ids)
            cached_match_count = self._count_cached_matches(cached_matches, match_ids)

            avg_game_seconds = 0.0
            if cached_match_count > 0:
                avg_game_seconds = total_seconds_observed / cached_match_count

            mastery_level_score = 0
            total_mastery_points = 0
            mastery_game_estimate = 0
            estimated_missing_games = 0
            estimated_extra_seconds = 0
            used_mastery_estimate = False
            mastery_estimate_available = False

            if self.use_mastery_estimate and cached_match_count > 0:
                try:
                    mastery_level_score = self._fetch_mastery_level_score_by_puuid(puuid)
                except (RuntimeError, TypeError, ValueError) as exc:
                    if self.debug:
                        print(f"[LOL DEBUG] échec récupération mastery score (levels): {exc}")

                try:
                    total_mastery_points = self._fetch_total_mastery_points_by_puuid(puuid)
                    mastery_estimate_available = total_mastery_points > 0

                    mastery_game_estimate = (
                        total_mastery_points // self.mastery_points_per_estimated_game
                    )

                    estimated_missing_games = max(
                        0,
                        mastery_game_estimate - cached_match_count,
                    )

                    estimated_extra_seconds = round(
                        estimated_missing_games * avg_game_seconds
                    )

                    used_mastery_estimate = (
                        estimated_missing_games > 0 and estimated_extra_seconds > 0
                    )

                except (RuntimeError, TypeError, ValueError) as exc:
                    if self.debug:
                        print(f"[LOL DEBUG] échec récupération mastery points par puuid: {exc}")

            final_total_seconds = total_seconds_observed + estimated_extra_seconds
            playtime_hours = round(final_total_seconds / 3600, 2)

            queue_counts = self._build_meta_counts(cached_matches, match_ids, "queue_id")
            game_mode_counts = self._build_meta_counts(
                cached_matches, match_ids, "game_mode"
            )
            game_type_counts = self._build_meta_counts(
                cached_matches, match_ids, "game_type"
            )
            map_counts = self._build_meta_counts(cached_matches, match_ids, "map_id")

            if self.debug:
                print(f"[LOL DEBUG] total_seconds_observed={total_seconds_observed}")
                print(f"[LOL DEBUG] cached_match_count(valide)={cached_match_count}")
                print(f"[LOL DEBUG] avg_game_seconds={round(avg_game_seconds, 2)}")
                print(f"[LOL DEBUG] mastery_level_score={mastery_level_score}")
                print(f"[LOL DEBUG] total_mastery_points={total_mastery_points}")
                print(f"[LOL DEBUG] mastery_game_estimate={mastery_game_estimate}")
                print(f"[LOL DEBUG] estimated_missing_games={estimated_missing_games}")
                print(f"[LOL DEBUG] estimated_extra_seconds={estimated_extra_seconds}")
                print(f"[LOL DEBUG] final_total_seconds={final_total_seconds}")
                print(f"[LOL DEBUG] playtime_hours={playtime_hours}")

                self._print_meta_summary("queue_id", queue_counts)
                self._print_meta_summary("game_mode", game_mode_counts)
                self._print_meta_summary("game_type", game_type_counts)
                self._print_meta_summary("map_id", map_counts)

            confidence = 0.2
            if cached_match_count >= 200:
                confidence = 0.9
            elif cached_match_count >= 50:
                confidence = 0.8
            elif cached_match_count >= 10:
                confidence = 0.65
            elif cached_match_count > 0:
                confidence = 0.45

            if used_mastery_estimate:
                estimated_share = 0.0
                if final_total_seconds > 0:
                    estimated_share = estimated_extra_seconds / final_total_seconds

                if estimated_share >= 0.7:
                    confidence = min(confidence, 0.45)
                elif estimated_share >= 0.5:
                    confidence = min(confidence, 0.55)
                elif estimated_share >= 0.3:
                    confidence = min(confidence, 0.65)
                else:
                    confidence = min(confidence, 0.75)

            source_detail = "estimated from cached Riot LoL match durations"
            if used_mastery_estimate:
                source_detail += " + mastery points fallback estimate"

            game = NormalizedGame(
                name="League of Legends",
                platform="riot",
                playtime_hours=playtime_hours,
                launcher="riot",
                source="api",
                source_detail=source_detail,
                is_estimated=True,
                confidence=confidence,
                raw_data={
                    "match_count_requested": len(match_ids),
                    "cached_match_count": cached_match_count,
                    "new_matches_added": added_count,
                    "new_matches_skipped": skipped_count,
                    "total_seconds_observed": total_seconds_observed,
                    "final_total_seconds": final_total_seconds,
                    "avg_game_seconds_observed": round(avg_game_seconds, 2),
                    "max_matches": self.max_matches,
                    "batch_size": self.batch_size,
                    "platform_region": self.platform_region,
                    "use_mastery_estimate": self.use_mastery_estimate,
                    "mastery_points_per_estimated_game": self.mastery_points_per_estimated_game,
                    "mastery_level_score": mastery_level_score,
                    "total_mastery_points": total_mastery_points,
                    "mastery_estimate_available": mastery_estimate_available,
                    "mastery_game_estimate": mastery_game_estimate,
                    "estimated_missing_games": estimated_missing_games,
                    "estimated_extra_seconds": estimated_extra_seconds,
                    "used_mastery_estimate": used_mastery_estimate,
                    "queue_counts": queue_counts,
                    "game_mode_counts": game_mode_counts,
                    "game_type_counts": game_type_counts,
                    "map_counts": map_counts,
                },
            )

            duration = perf_counter() - start_timer
            finished_at = self.now_iso()

            result = self.build_success_result(
                total_games_found=1,
                total_games_imported=1,
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                raw_summary={
                    "puuid": puuid,
                    "match_count_requested": len(match_ids),
                    "cached_match_count": cached_match_count,
                    "new_matches_added": added_count,
                    "new_matches_skipped": skipped_count,
                    "playtime_hours": playtime_hours,
                    "max_matches": self.max_matches,
                    "batch_size": self.batch_size,
                    "platform_region": self.platform_region,
                    "use_mastery_estimate": self.use_mastery_estimate,
                    "mastery_points_per_estimated_game": self.mastery_points_per_estimated_game,
                    "mastery_level_score": mastery_level_score,
                    "total_mastery_points": total_mastery_points,
                    "mastery_estimate_available": mastery_estimate_available,
                    "mastery_game_estimate": mastery_game_estimate,
                    "estimated_missing_games": estimated_missing_games,
                    "estimated_extra_seconds": estimated_extra_seconds,
                    "used_mastery_estimate": used_mastery_estimate,
                    "queue_counts": queue_counts,
                    "game_mode_counts": game_mode_counts,
                    "game_type_counts": game_type_counts,
                    "map_counts": map_counts,
                },
            )

            if len(match_ids) == 0:
                result.add_warning("Aucun match trouvé pour ce compte")

            if skipped_count > 0:
                result.add_warning(
                    f"{skipped_count} nouveau(x) match(s) ignoré(s) pendant l'analyse"
                )

            if added_count == 0 and len(new_match_ids) == 0:
                result.add_warning("Aucun nouveau match à synchroniser, cache déjà à jour")

            if self.use_mastery_estimate and not used_mastery_estimate:
                result.add_warning(
                    "estimation mastery non appliquée: points de mastery insuffisants ou endpoint incompatible"
                )

            if self.debug:
                print("[LOL DEBUG] ===============================================")
                print("[LOL DEBUG] FIN COLLECTE LOL")
                print(f"[LOL DEBUG] durée totale={round(duration, 2)}s")
                print("[LOL DEBUG] ===============================================")

            return [game], result

        except (RuntimeError, OSError, TypeError, ValueError, KeyError) as exc:
            duration = perf_counter() - start_timer
            finished_at = self.now_iso()

            if self.debug:
                print("[LOL DEBUG] ===============================================")
                print("[LOL DEBUG] ECHEC COLLECTE LOL")
                print(f"[LOL DEBUG] erreur={exc}")
                print("[LOL DEBUG] ===============================================")

            result = self.build_failure_result(
                error_message=str(exc),
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                raw_summary={
                    "puuid": account.account_id,
                    "max_matches": self.max_matches,
                    "batch_size": self.batch_size,
                    "platform_region": self.platform_region,
                    "use_mastery_estimate": self.use_mastery_estimate,
                    "mastery_points_per_estimated_game": self.mastery_points_per_estimated_game,
                },
            )

            return [], result

    def _fetch_all_match_ids(
        self,
        puuid: str,
        batch_size: int = 100,
        max_matches: int | None = None,
    ) -> list[str]:
        all_match_ids: list[str] = []
        start = 0
        page_index = 0

        if self.debug:
            print("[LOL DEBUG] --- début pagination match ids ---")
            print(f"[LOL DEBUG] puuid={puuid}")
            print(f"[LOL DEBUG] batch_size={batch_size}")
            print(f"[LOL DEBUG] max_matches={max_matches}")

        while True:
            if max_matches is not None:
                remaining = max_matches - len(all_match_ids)
                if remaining <= 0:
                    if self.debug:
                        print("[LOL DEBUG] arrêt pagination: limite max_matches atteinte")
                        print(f"[LOL DEBUG] total accumulé={len(all_match_ids)}")
                    break
                count = min(batch_size, remaining)
            else:
                remaining = None
                count = batch_size

            url = (
                f"https://{self.region}.api.riotgames.com/"
                f"lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}"
            )

            if self.debug:
                print("[LOL DEBUG] -----------------------------------------------")
                print(f"[LOL DEBUG] page_index={page_index}")
                print(f"[LOL DEBUG] start={start}")
                print(f"[LOL DEBUG] remaining={remaining}")
                print(f"[LOL DEBUG] requested_count={count}")
                print(f"[LOL DEBUG] url={url}")

            data = self._get_json(url)

            if not isinstance(data, list):
                raise TypeError("Format inattendu pour la liste des matchs LoL")

            received = len(data)

            if self.debug:
                print(f"[LOL DEBUG] received_count={received}")
                if received > 0:
                    print(f"[LOL DEBUG] first_id_of_batch={data[0]}")
                    print(f"[LOL DEBUG] last_id_of_batch={data[-1]}")

            if not data:
                if self.debug:
                    print("[LOL DEBUG] arrêt pagination: Riot a renvoyé une liste vide")
                break

            all_match_ids.extend(data)

            if self.debug:
                print(f"[LOL DEBUG] total accumulé après page={len(all_match_ids)}")

            if len(data) < count:
                if self.debug:
                    print("[LOL DEBUG] arrêt pagination: Riot a renvoyé moins d'ids que demandé")
                    print(f"[LOL DEBUG] len(data)={len(data)} < requested_count={count}")
                break

            start += len(data)
            page_index += 1

        if self.debug:
            print("[LOL DEBUG] --- fin pagination match ids ---")
            print(f"[LOL DEBUG] total final récupéré={len(all_match_ids)}")

        return all_match_ids

    def _fetch_and_store_new_match_data(
        self,
        new_match_ids: list[str],
        cached_matches: dict,
    ) -> tuple[int, int]:
        added_count = 0
        skipped_count = 0

        if self.debug:
            print("[LOL DEBUG] --- début fetch détails matchs ---")
            print(f"[LOL DEBUG] nb nouveaux matchs à fetch={len(new_match_ids)}")

        for index, match_id in enumerate(new_match_ids, start=1):
            try:
                if self.debug:
                    print("[LOL DEBUG] -----------------------------------------------")
                    print(f"[LOL DEBUG] fetch match {index}/{len(new_match_ids)} : {match_id}")

                match_data = self._fetch_match_details(match_id)
                duration_seconds = self._extract_game_duration(match_data)
                meta = self._extract_match_meta(match_data)

                if self.debug:
                    metadata = match_data.get("metadata") or {}
                    info = match_data.get("info") or {}

                    participants = info.get("participants") or []
                    participant_count = (
                        len(participants) if isinstance(participants, list) else 0
                    )

                    print(
                        f"[LOL DEBUG] {match_id} -> "
                        f"duration={duration_seconds}, "
                        f"queue={meta['queue_id']}, "
                        f"mode={meta['game_mode']}, "
                        f"type={meta['game_type']}, "
                        f"map={meta['map_id']}, "
                        f"participants={participant_count}, "
                        f"gameCreation={info.get('gameCreation')}, "
                        f"gameEndTimestamp={info.get('gameEndTimestamp')}, "
                        f"dataVersion={metadata.get('dataVersion')}"
                    )

                if duration_seconds <= 0:
                    if self.debug:
                        print(f"[LOL DEBUG] match ignoré: durée invalide pour {match_id}")
                        print(f"[LOL DEBUG] payload keys top-level={list(match_data.keys())}")
                        info = match_data.get("info") or {}
                        print(
                            "[LOL DEBUG] payload info keys="
                            f"{list(info.keys()) if isinstance(info, dict) else 'N/A'}"
                        )
                    skipped_count += 1
                    continue

                cached_matches[match_id] = {
                    "duration_seconds": duration_seconds,
                    "queue_id": meta["queue_id"],
                    "game_mode": meta["game_mode"],
                    "game_type": meta["game_type"],
                    "map_id": meta["map_id"],
                }
                added_count += 1

            except (RuntimeError, OSError, TypeError, ValueError, KeyError) as exc:
                if self.debug:
                    print(f"[LOL DEBUG] erreur pour {match_id}: {exc}")
                skipped_count += 1

        if self.debug:
            print("[LOL DEBUG] --- fin fetch détails matchs ---")
            print(f"[LOL DEBUG] ajoutés={added_count}")
            print(f"[LOL DEBUG] ignorés={skipped_count}")

        return added_count, skipped_count

    def _fetch_match_details(self, match_id: str) -> dict:
        url = (
            f"https://{self.region}.api.riotgames.com/"
            f"lol/match/v5/matches/{match_id}"
        )

        if self.debug:
            print(f"[LOL DEBUG] détails url={url}")

        data = self._get_json(url)

        if not isinstance(data, dict):
            raise TypeError(f"Format inattendu pour le match LoL {match_id}")

        return data

    def _fetch_mastery_level_score_by_puuid(self, puuid: str) -> int:
        url = (
            f"https://{self.platform_region}.api.riotgames.com/"
            f"lol/champion-mastery/v4/scores/by-puuid/{puuid}"
        )

        if self.debug:
            print(f"[LOL DEBUG] mastery-by-puuid score url={url}")

        data = self._get_json(url)

        try:
            score = int(data)
        except (TypeError, ValueError):
            raise RuntimeError("Score de mastery invalide")

        if self.debug:
            print(f"[LOL DEBUG] mastery-by-puuid score={score}")

        return max(0, score)

    def _fetch_total_mastery_points_by_puuid(self, puuid: str) -> int:
        url = (
            f"https://{self.platform_region}.api.riotgames.com/"
            f"lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}"
        )

        if self.debug:
            print(f"[LOL DEBUG] mastery-by-puuid list url={url}")

        data = self._get_json(url)

        if not isinstance(data, list):
            raise TypeError("Format inattendu pour la liste de champion masteries")

        total_points = 0

        for item in data:
            if not isinstance(item, dict):
                continue

            try:
                total_points += int(item.get("championPoints", 0))
            except (TypeError, ValueError):
                continue

        if self.debug:
            print(f"[LOL DEBUG] mastery-by-puuid total_points={total_points}")
            print(f"[LOL DEBUG] mastery-by-puuid champions_count={len(data)}")

        return max(0, total_points)

    def _extract_game_duration(self, match_data: dict) -> int:
        info = match_data.get("info") or {}

        duration = info.get("gameDuration")
        if duration is None:
            if self.debug:
                print("[LOL DEBUG] gameDuration absent")
            return 0

        try:
            duration = int(duration)
        except (TypeError, ValueError):
            if self.debug:
                print(f"[LOL DEBUG] gameDuration non convertible: {duration}")
            return 0

        if duration <= 0:
            if self.debug:
                print(f"[LOL DEBUG] gameDuration <= 0: {duration}")
            return 0

        if duration > 100000:
            if self.debug:
                print(f"[LOL DEBUG] gameDuration semble en ms: {duration} -> conversion secondes")
            duration = duration // 1000

        return duration

    def _extract_match_meta(self, match_data: dict) -> dict:
        info = match_data.get("info") or {}

        return {
            "queue_id": info.get("queueId"),
            "game_mode": info.get("gameMode"),
            "game_type": info.get("gameType"),
            "map_id": info.get("mapId"),
        }

    def _sum_cached_durations(self, cached_matches: dict, match_ids: list[str]) -> int:
        total_seconds = 0

        for match_id in match_ids:
            match_entry = cached_matches.get(match_id)

            if isinstance(match_entry, dict):
                duration = match_entry.get("duration_seconds")
            else:
                duration = match_entry

            try:
                duration = int(duration)
            except (TypeError, ValueError):
                continue

            if duration > 0:
                total_seconds += duration

        return total_seconds

    def _count_cached_matches(self, cached_matches: dict, match_ids: list[str]) -> int:
        count = 0

        for match_id in match_ids:
            match_entry = cached_matches.get(match_id)

            if isinstance(match_entry, dict):
                duration = match_entry.get("duration_seconds")
            else:
                duration = match_entry

            try:
                duration = int(duration)
            except (TypeError, ValueError):
                continue

            if duration > 0:
                count += 1

        return count

    def _build_meta_counts(self, cached_matches: dict, match_ids: list[str], key: str) -> dict:
        counts: dict[str, int] = {}

        for match_id in match_ids:
            match_entry = cached_matches.get(match_id)

            if not isinstance(match_entry, dict):
                continue

            value = match_entry.get(key)
            value_key = str(value)

            counts[value_key] = counts.get(value_key, 0) + 1

        return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))

    def _print_meta_summary(self, label: str, counts: dict) -> None:
        print(f"[LOL DEBUG] résumé {label} :")

        if not counts:
            print("[LOL DEBUG]   aucun résultat")
            return

        for key, value in counts.items():
            print(f"[LOL DEBUG]   {key}: {value}")