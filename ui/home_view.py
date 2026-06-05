import customtkinter as ctk


class HomeView(ctk.CTkFrame):
    def __init__(self, master, on_import):
        super().__init__(master)

        self.on_import = on_import

        self.title_label = ctk.CTkLabel(
            self,
            text="Athena",
            font=ctk.CTkFont(size=34, weight="bold"),
        )
        self.title_label.pack(pady=(40, 8))

        self.subtitle_label = ctk.CTkLabel(
            self,
            text="Agrège tes heures de jeu depuis plusieurs plateformes",
            font=ctk.CTkFont(size=15),
            text_color=("gray35", "gray70"),
        )
        self.subtitle_label.pack(pady=(0, 28))

        self.hero_card = ctk.CTkFrame(self, corner_radius=18)
        self.hero_card.pack(padx=20, pady=10, fill="x")

        self.hero_text = ctk.CTkLabel(
            self.hero_card,
            text=(
                "Sources activées : Steam, osu!\n"
                "Clique pour importer tes données et afficher tes statistiques globales."
            ),
            justify="left",
            font=ctk.CTkFont(size=15),
        )
        self.hero_text.pack(anchor="w", padx=20, pady=20)

        self.import_button = ctk.CTkButton(
            self,
            text="Importer mes données",
            command=self._handle_import,
            width=260,
            height=46,
        )
        self.import_button.pack(pady=18)

        self.status_label = ctk.CTkLabel(
            self,
            text="Aucune synchronisation lancée.",
            font=ctk.CTkFont(size=14),
        )
        self.status_label.pack(pady=(8, 10))

    def _handle_import(self):
        self.set_status("Import en cours...")
        self.import_button.configure(state="disabled", text="Import...")
        self.update_idletasks()
        self.on_import()

    def set_status(self, message: str):
        self.status_label.configure(text=message)

    def set_idle(self):
        self.import_button.configure(state="normal", text="Importer mes données")