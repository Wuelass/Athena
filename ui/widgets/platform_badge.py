"""Reusable badge widget for displaying a gaming platform.

Responsibilities:
- Render a compact platform identifier inside Athena views.
- Centralize the visual representation reused across presentation screens.
- Keep platform badge styling out of higher-level view classes.
- Provide one small widget with a focused presentation responsibility.
Architecture notes:
- Reuse avoids duplicating layout and styling code between views.
- The widget consumes already-normalized display values.
- It contains no collection, persistence or business behaviour.
- Changes to badge appearance remain isolated to this file.
- The component follows the single-responsibility principle.
"""

from typing import ClassVar

import customtkinter as ctk


class PlatformBadge(ctk.CTkLabel):
    PLATFORM_COLORS: ClassVar[dict[str, tuple[str, str]]] = {
        "steam": ("#1b2838", "#1b2838"),
        "osu": ("#ff66aa", "#ff66aa"),
        "riot": ("#cc2936", "#cc2936"),
        "epic": ("#2a2a2a", "#2a2a2a"),
        "unknown": ("#666666", "#666666"),
    }

    def __init__(self, master, platform: str):
        platform_key = (platform or "unknown").strip().lower()
        fg_color = self.PLATFORM_COLORS.get(platform_key, self.PLATFORM_COLORS["unknown"])

        super().__init__(
            master,
            text=platform_key.upper(),
            corner_radius=999,
            padx=12,
            pady=4,
            fg_color=fg_color,
            text_color="white",
            font=ctk.CTkFont(size=12, weight="bold"),
        )