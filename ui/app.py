import customtkinter as ctk
from config import (
    OSU_CLIENT_ID,
    OSU_CLIENT_SECRET,
    OSU_USER_ID,
    STEAM_API_KEY,
    STEAM_ID,
)

from collectors.osu_collector import OsuCollector
from collectors.steam_collector import SteamCollector
from models.platform_account import PlatformAccount
from services.import_service import ImportService
from services.merge_service import MergeService
from services.stats_service import StatsService
from ui.home_view import HomeView
from ui.library_view import LibraryView
from ui.stats_view import StatsView


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Athena")
        self.geometry("1100x760")
        self.minsize(940, 680)

        self.import_service = ImportService()
        self.merge_service = MergeService()
        self.stats_service = StatsService()

        self.steam_collector = SteamCollector(api_key=STEAM_API_KEY)
        self.osu_collector = OsuCollector(
            client_id=OSU_CLIENT_ID,
            client_secret=OSU_CLIENT_SECRET,
        )

        self.steam_account = PlatformAccount.from_steam(
            steam_id=STEAM_ID,
            username="SteamUser",
        )
        self.osu_account = PlatformAccount.from_osu(
            user_id=OSU_USER_ID,
            username="OsuUser",
        )

        self.current_games = []
        self.current_summary = None

        self.home_view = HomeView(self, on_import=self.run_import)
        self.stats_view = StatsView(
            self,
            on_back=self.show_home,
            on_open_library=self.show_library,
        )
        self.library_view = LibraryView(
            self,
            on_back=self.show_stats,
        )

        self.show_home()

    def _hide_all_views(self):
        self.home_view.pack_forget()
        self.stats_view.pack_forget()
        self.library_view.pack_forget()

    def show_home(self):
        self._hide_all_views()
        self.home_view.pack(fill="both", expand=True)
        self.home_view.set_idle()

    def show_stats(self):
        self._hide_all_views()
        self.stats_view.pack(fill="both", expand=True)

    def show_library(self):
        self._hide_all_views()
        self.library_view.pack(fill="both", expand=True)

    def run_import(self):
        try:
            reports = self.import_service.import_many([
                (self.steam_collector, self.steam_account),
                (self.osu_collector, self.osu_account),
            ])

            failed_platforms = []
            for report in reports:
                if report.sync_result and not report.sync_result.success:
                    failed_platforms.append(report.sync_result.platform)

            merge_result = self.merge_service.merge_reports(reports)
            merged_games = merge_result.merged_games

            if not merged_games:
                self.home_view.set_status("Import terminé, mais aucune donnée exploitable.")
                self.home_view.set_idle()
                return

            summary = self.stats_service.build_summary(merged_games)

            self.current_games = merged_games
            self.current_summary = summary

            self.stats_view.update_stats(summary)
            self.library_view.update_library(merged_games)

            status_message = (
                f"Import terminé : {summary.total_games} jeux, "
                f"{summary.total_playtime_hours} h"
            )

            if failed_platforms:
                status_message += f" | échecs: {', '.join(failed_platforms)}"

            self.home_view.set_status(status_message)
            self.home_view.set_idle()
            self.show_stats()

        except Exception as exc:  # noqa: BLE001
            self.home_view.set_status(f"Erreur inattendue : {exc}")
            self.home_view.set_idle()


def run_app():
    app = App()
    app.mainloop()