"""Library view displaying normalized games in Athena.

Responsibilities:
- Render the merged collection of normalized game records.
- Present platform and playtime information in a readable layout.
- Refresh displayed content when application state changes.
- Keep display formatting out of business and collection services.
Architecture notes:
- The view consumes normalized models produced by the service layer.
- It does not need to understand Steam, Riot, osu! or Xbox APIs.
- Widget creation remains isolated in the presentation layer.
- Data transformations required for business rules occur before rendering.
- This separation allows presentation changes without collector changes.
"""

import customtkinter as ctk

from ui.widgets.platform_badge import PlatformBadge


class LibraryView(ctk.CTkFrame):
    def __init__(self, master, on_back):
        super().__init__(master)

        self.on_back = on_back
        self.current_games = []

        self.title_label = ctk.CTkLabel(
            self,
            text="Bibliothèque",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.title_label.pack(pady=(24, 10))

        self.info_label = ctk.CTkLabel(
            self,
            text="Aucune donnée chargée.",
            font=ctk.CTkFont(size=14),
        )
        self.info_label.pack(pady=(0, 12))

        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.sort_label = ctk.CTkLabel(
            controls_frame,
            text="Tri :",
            font=ctk.CTkFont(size=14),
        )
        self.sort_label.pack(side="left", padx=(0, 8))

        self.sort_menu = ctk.CTkOptionMenu(
            controls_frame,
            values=[
                "Temps de jeu décroissant",
                "Temps de jeu croissant",
                "Nom A-Z",
                "Nom Z-A",
            ],
            command=self._on_sort_changed,
            width=220,
        )
        self.sort_menu.pack(side="left")

        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=16)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.back_button = ctk.CTkButton(
            self,
            text="Retour",
            command=self.on_back,
            width=180,
            height=40,
        )
        self.back_button.pack(pady=(10, 24))

    def update_library(self, games: list) -> None:
        self.current_games = list(games)
        self.info_label.configure(text=f"{len(self.current_games)} jeux chargés")
        self._render_games()

    def _on_sort_changed(self, _value: str) -> None:
        self._render_games()

    def _sorted_games(self) -> list:
        games = list(self.current_games)
        mode = self.sort_menu.get()

        if mode == "Temps de jeu décroissant":
            games.sort(key=lambda game: game.playtime_hours, reverse=True)
        elif mode == "Temps de jeu croissant":
            games.sort(key=lambda game: game.playtime_hours)
        elif mode == "Nom A-Z":
            games.sort(key=lambda game: game.name.lower())
        elif mode == "Nom Z-A":
            games.sort(key=lambda game: game.name.lower(), reverse=True)

        return games

    def _render_games(self) -> None:
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        for game in self._sorted_games():
            card = ctk.CTkFrame(self.scroll_frame, corner_radius=14)
            card.pack(fill="x", padx=6, pady=6)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=14, pady=(12, 6))

            name_label = ctk.CTkLabel(
                top_row,
                text=game.name,
                font=ctk.CTkFont(size=18, weight="bold"),
            )
            name_label.pack(side="left")

            badge = PlatformBadge(top_row, game.platform)
            badge.pack(side="right")

            bottom_row = ctk.CTkFrame(card, fg_color="transparent")
            bottom_row.pack(fill="x", padx=14, pady=(0, 12))

            playtime_label = ctk.CTkLabel(
                bottom_row,
                text=f"{game.playtime_hours} h",
                font=ctk.CTkFont(size=15),
            )
            playtime_label.pack(side="left")

            source_parts = [game.source]
            if game.is_estimated:
                source_parts.append("estimé")

            source_text = " • ".join(part for part in source_parts if part)
            source_label = ctk.CTkLabel(
                bottom_row,
                text=source_text,
                font=ctk.CTkFont(size=13),
                text_color=("gray35", "gray70"),
            )
            source_label.pack(side="right")