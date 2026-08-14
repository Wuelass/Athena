"""Application entry point for Athena.

Responsibilities:
- Build the platform collectors used by the command-line flow.
- Instantiate the reusable import, merge and statistics services.
- Coordinate collection without embedding platform-specific logic.
- Convert collected values into normalized domain objects.
Architecture notes:
- External access remains isolated in collector classes.
- Business operations remain delegated to service classes.
- Models carry normalized data between application layers.
- Configuration values are read from the dedicated config module.
- This module focuses on orchestration rather than business rules.
"""

from collectors.epic.epic_collector import EpicCollector
from collectors.osu_collector import OsuCollector
from collectors.riot.lol_collector import LoLCollector
from collectors.riot.valorant_collector import ValorantCollector
from collectors.steam_collector import SteamCollector
from config import (
    EPIC_DEBUG,
    EPIC_ENABLE_LOG_ESTIMATE,
    EPIC_MAX_SESSION_HOURS,
    EPIC_SAVED_DIR,
    OSU_CLIENT_ID,
    OSU_CLIENT_SECRET,
    OSU_USER_ID,
    RIOT_API_KEY,
    RIOT_BATCH_SIZE,
    RIOT_DEBUG,
    RIOT_GAME_NAME,
    RIOT_MASTERY_POINTS_PER_ESTIMATED_GAME,
    RIOT_MATCH_ROUTE,
    RIOT_MAX_MATCHES,
    RIOT_PLATFORM_REGION,
    RIOT_PUUID,
    RIOT_TAG,
    RIOT_USE_MASTERY_ESTIMATE,
    RIOT_VAL_REGION,
    STEAM_API_KEY,
    STEAM_ID,
)
from models.platform_account import PlatformAccount
from services.import_service import ImportService
from services.merge_service import MergeService
from services.stats_service import StatsService


def main() -> None:
    import_service = ImportService()
    stats_service = StatsService()
    merge_service = MergeService()

    steam_collector = SteamCollector(api_key=STEAM_API_KEY)
    osu_collector = OsuCollector(
        client_id=OSU_CLIENT_ID,
        client_secret=OSU_CLIENT_SECRET,
    )

    _lol_collector = LoLCollector(
        api_key=RIOT_API_KEY,
        region=RIOT_MATCH_ROUTE,
        platform_region=RIOT_PLATFORM_REGION,
        max_matches=RIOT_MAX_MATCHES,
        batch_size=RIOT_BATCH_SIZE,
        debug=RIOT_DEBUG,
        use_mastery_estimate=RIOT_USE_MASTERY_ESTIMATE,
        mastery_points_per_estimated_game=RIOT_MASTERY_POINTS_PER_ESTIMATED_GAME,
    )

    _valorant_collector = ValorantCollector(
        api_key=RIOT_API_KEY,
        region=RIOT_VAL_REGION,
        debug=RIOT_DEBUG,
    )

    _epic_collector = EpicCollector(
        saved_dir=EPIC_SAVED_DIR,
        debug=EPIC_DEBUG,
        enable_log_estimate=EPIC_ENABLE_LOG_ESTIMATE,
        max_session_hours=EPIC_MAX_SESSION_HOURS,
    )

    steam_account = PlatformAccount.from_steam(
        steam_id=STEAM_ID,
        username="SteamUser",
    )

    osu_account = PlatformAccount.from_osu(
        user_id=OSU_USER_ID,
        username="OsuUser",
    )

    _riot_account = PlatformAccount.from_riot(
        puuid=RIOT_PUUID,
        game_name=RIOT_GAME_NAME,
        tag=RIOT_TAG,
        region=RIOT_MATCH_ROUTE,
    )

    _valorant_account = PlatformAccount(
        platform="riot",
        account_id="tracker:valorant:softcult-naive",
        username="SoftCult",
        display_name="SoftCult#NAIVE",
        region=RIOT_VAL_REGION,
        tag="NAIVE",
        is_active=True,
        is_connected=True,
        raw_data={
            "tracker_url": (
                "https://tracker.gg/valorant/profile/riot/"
                "SoftCult%23NAIVE/performance?platform=pc"
                "&playlist=competitive&season=9d85c932-4820-c060-09c3-668636d4df1b"
            ),
            "game_name": "SoftCult",
            "tag": "NAIVE",
        },
    )

    _epic_account = PlatformAccount(
        platform="epic",
        account_id="local_epic_launcher",
        username="EpicLocal",
        display_name="Epic Local",
        is_active=True,
        is_connected=True,
    )

    reports = import_service.import_many([
        (steam_collector, steam_account),
        (osu_collector, osu_account),
        # (_lol_collector, _riot_account),
        # (_valorant_collector, _valorant_account),
        # (_epic_collector, _epic_account),
    ])

    print("=" * 60)
    print("RÉSULTATS PAR PLATEFORME")
    print("=" * 60)

    for report in reports:
        result = report.sync_result

        if not result:
            print("Aucun résultat.")
            continue

        print(f"\nPlateforme : {result.platform}")
        print(f"Succès : {result.success}")
        print(f"Jeux trouvés : {result.total_games_found}")
        print(f"Jeux importés : {result.total_games_imported}")
        print(f"Durée : {result.duration_seconds} s")

        if result.platform == "riot" and report.games:
            game = report.games[0]
            raw = game.raw_data or {}

            if game.name == "League of Legends":
                observed_seconds = raw.get("total_seconds_observed", 0)
                final_seconds = raw.get("final_total_seconds", observed_seconds)
                match_count = raw.get("cached_match_count", 0)
                used_mastery = raw.get("used_mastery_estimate", False)

                observed_hours = round(observed_seconds / 3600, 2)
                final_hours = round(final_seconds / 3600, 2)

                print("---- Détail LoL ----")
                print(f"Heures observées : {observed_hours} h")
                print(f"Heures finales : {final_hours} h")
                print(f"Matchs valides observés : {match_count}")
                print(f"Estimation mastery utilisée : {used_mastery}")

            elif game.name == "VALORANT":
                print("---- Détail VALORANT ----")
                print(f"Heures : {game.playtime_hours} h")
                print(f"Source : {game.source_detail}")

                matches_played = raw.get("matches_played")
                wins = raw.get("wins")
                tracker_url = raw.get("tracker_url")

                if matches_played is not None:
                    print(f"Matches joués : {matches_played}")

                if wins is not None:
                    print(f"Wins : {wins}")

                if tracker_url:
                    print(f"Tracker URL : {tracker_url}")

        elif result.platform == "epic" and report.games:
            print("---- Détail EPIC ----")
            for game in report.games:
                raw = game.raw_data or {}

                print(f"- {game.name} : {game.playtime_hours} h")
                print(f"  Source : {game.source_detail}")

                app_name = raw.get("app_name")
                session_count = raw.get("session_count")
                install_location = raw.get("install_location")

                if app_name:
                    print(f"  App name : {app_name}")

                if session_count is not None:
                    print(f"  Sessions estimées : {session_count}")

                if install_location:
                    print(f"  Install location : {install_location}")

        if result.errors:
            print("Erreurs :")
            for err in result.errors:
                print(f"- {err}")

        if result.warnings:
            print("Warnings :")
            for warn in result.warnings:
                print(f"- {warn}")

    merge_result = merge_service.merge_reports(reports)
    all_games = merge_result.merged_games

    print("\n" + "=" * 60)
    print("FUSION")
    print("=" * 60)
    print(f"Jeux fusionnés : {merge_result.total_games()}")
    print(f"Doublons retirés : {merge_result.duplicates_removed}")
    print(f"Entrées invalides ignorées : {merge_result.invalid_entries_skipped}")

    if not all_games:
        print("\nAucune donnée globale.")
        return

    summary = stats_service.build_summary(all_games)

    print("\n" + "=" * 60)
    print("STATISTIQUES GLOBALES")
    print("=" * 60)

    print(f"Total jeux : {summary.total_games}")
    print(f"Heures totales : {summary.total_playtime_hours}")
    print(f"Moyenne : {summary.average_playtime_hours}")
    print(f"Jeux estimés : {summary.estimated_games_count}")

    print("\nTop jeux :")
    for i, game in enumerate(summary.top_games, start=1):
        print(f"{i}. {game.name} ({game.platform}) - {game.playtime_hours} h")

    print("\nRépartition par plateforme :")
    for platform, data in summary.platform_breakdown.items():
        print(
            f"- {platform}: {data['game_count']} jeux, "
            f"{data['total_playtime_hours']} h"
        )

if __name__ == "__main__":
    main()