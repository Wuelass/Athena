"""Statistics view for the Athena graphical interface.

Responsibilities:
- Display summary values produced by the statistics service.
- Render platform-level indicators using reusable UI widgets.
- Refresh statistics when the current application summary changes.
- Keep visual formatting separate from calculation rules.
Architecture notes:
- Statistical calculations are completed by ``StatsService``.
- The view only consumes the resulting summary structure.
- Reusable cards and badges reduce duplicated presentation code.
- No external platform API is accessed from this component.
- The class belongs exclusively to the presentation layer.
"""

import customtkinter as ctk

from ui.widgets.platform_badge import PlatformBadge
from ui.widgets.stat_card import StatCard


class StatsView(ctk.CTkFrame):
    def __init__(self, master, on_back, on_open_library):
        super().__init__(master)

        self.on_back = on_back
        self.on_open_library = on_open_library

        self.title_label = ctk.CTkLabel(
            self,
            text="Statistiques globales",
            font=ctk.CTkFont(size=30, weight="bold"),
        )
        self.title_label.pack(pady=(24, 8))

        self.subtitle_label = ctk.CTkLabel(
            self,
            text="Vue d’ensemble de tes heures de jeu",
            font=ctk.CTkFont(size=14),
            text_color=("gray35", "gray70"),
        )
        self.subtitle_label.pack(pady=(0, 16))

        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.pack(fill="x", padx=20, pady=8)

        self.cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.total_games_card = StatCard(self.cards_frame, "Jeux", "0")
        self.total_games_card.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        self.total_hours_card = StatCard(self.cards_frame, "Heures totales", "0.0")
        self.total_hours_card.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        self.average_card = StatCard(self.cards_frame, "Moyenne / jeu", "0.0")
        self.average_card.grid(row=0, column=2, padx=8, pady=8, sticky="ew")

        self.estimated_card = StatCard(self.cards_frame, "Jeux estimés", "0")
        self.estimated_card.grid(row=0, column=3, padx=8, pady=8, sticky="ew")

        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=10)

        content_frame.grid_columnconfigure((0, 1), weight=1)
        content_frame.grid_rowconfigure(0, weight=1)

        self.top_frame = ctk.CTkFrame(content_frame, corner_radius=16)
        self.top_frame.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="nsew")

        self.top_title = ctk.CTkLabel(
            self.top_frame,
            text="Top jeux",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.top_title.pack(anchor="w", padx=18, pady=(16, 12))

        self.top_games_box = ctk.CTkTextbox(self.top_frame, height=260)
        self.top_games_box.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.top_games_box.configure(state="disabled")

        self.platform_frame = ctk.CTkFrame(content_frame, corner_radius=16)
        self.platform_frame.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="nsew")

        self.platform_title = ctk.CTkLabel(
            self.platform_frame,
            text="Plateformes",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.platform_title.pack(anchor="w", padx=18, pady=(16, 12))

        self.platform_list = ctk.CTkScrollableFrame(self.platform_frame, height=260)
        self.platform_list.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_frame.pack(pady=(4, 24))

        self.library_button = ctk.CTkButton(
            self.actions_frame,
            text="Voir la bibliothèque",
            command=self.on_open_library,
            width=200,
            height=40,
        )
        self.library_button.pack(side="left", padx=8)

        self.back_button = ctk.CTkButton(
            self.actions_frame,
            text="Retour",
            command=self.on_back,
            width=160,
            height=40,
        )
        self.back_button.pack(side="left", padx=8)

    def update_stats(self, summary):
        self.total_games_card.set_value(str(summary.total_games))
        self.total_hours_card.set_value(str(summary.total_playtime_hours))
        self.average_card.set_value(str(summary.average_playtime_hours))
        self.estimated_card.set_value(str(summary.estimated_games_count))

        self.top_games_box.configure(state="normal")
        self.top_games_box.delete("0.0", "end")

        for index, game in enumerate(summary.top_games, start=1):
            self.top_games_box.insert(
                "end",
                f"{index}. {game.name}\n"
                f"   Plateforme : {game.platform}\n"
                f"   Temps : {game.playtime_hours} h\n\n",
            )

        self.top_games_box.configure(state="disabled")

        for widget in self.platform_list.winfo_children():
            widget.destroy()

        for platform, data in summary.platform_breakdown.items():
            row = ctk.CTkFrame(self.platform_list, corner_radius=12)
            row.pack(fill="x", pady=6)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=10)

            badge = PlatformBadge(left, platform)
            badge.pack(anchor="w")

            details = ctk.CTkLabel(
                left,
                text=f"{data['game_count']} jeux • {data['total_playtime_hours']} h",
                font=ctk.CTkFont(size=14),
            )
            details.pack(anchor="w", pady=(8, 0))