import customtkinter as ctk


class StatCard(ctk.CTkFrame):
    def __init__(self, master, title: str, value: str, width: int = 220, height: int = 120):
        super().__init__(master, width=width, height=height, corner_radius=16)

        self.grid_propagate(False)
        self.pack_propagate(False)

        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=14),
            text_color=("gray30", "gray70"),
        )
        self.title_label.pack(anchor="w", padx=18, pady=(16, 6))

        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.value_label.pack(anchor="w", padx=18, pady=(0, 16))

    def set_value(self, value: str) -> None:
        self.value_label.configure(text=value)