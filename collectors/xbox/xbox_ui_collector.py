import csv
import ctypes
import json
import time
from pathlib import Path

import pyautogui
from PIL import Image

from utils.ocr import clean_text, extract_playtime, image_to_text, playtime_to_hours


def enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class XboxUICollector:
    def __init__(
        self,
        game_name_region: tuple[int, int, int, int],
        playtime_region: tuple[int, int, int, int],
        output_dir: str = "data/xbox",
        open_delay: float = 5.0,
        back_delay: float = 3.0,
        move_delay: float = 1.5,
        initial_wait: float = 5.0,
        assume_first_game_already_selected: bool = True,
    ):
        self.game_name_region = game_name_region
        self.playtime_region = playtime_region
        self.output_dir = Path(output_dir)

        self.open_delay = open_delay
        self.back_delay = back_delay
        self.move_delay = move_delay
        self.initial_wait = initial_wait
        self.assume_first_game_already_selected = assume_first_game_already_selected

        self.screenshot_dir = self.output_dir / "screenshots"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.4

    def _capture_region(self, region: tuple[int, int, int, int]) -> Image.Image:
        return pyautogui.screenshot(region=region)

    def _focus_first_game_if_needed(self) -> None:
        if not self.assume_first_game_already_selected:
            pyautogui.press("tab")
            time.sleep(self.move_delay)

    def _open_selected_game(self) -> None:
        pyautogui.press("enter")
        time.sleep(self.open_delay)

    def _go_back(self) -> None:
        pyautogui.press("esc")
        time.sleep(self.back_delay)

    def _select_next_game(self) -> None:
        pyautogui.press("down")
        time.sleep(self.move_delay)

    def _save(self, data: list[dict]) -> None:
        json_path = self.output_dir / "xbox_data.json"
        csv_path = self.output_dir / "xbox_data.csv"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["platform", "game_name", "playtime_raw", "playtime_hours", "source"],
            )
            writer.writeheader()
            writer.writerows(data)

        print(f"💾 Sauvegardé dans {self.output_dir}")

    def collect(self, max_games: int = 50) -> list[dict]:
        results = []
        seen_names = set()

        print("⏳ Mets-toi sur la page Xbox avec le premier jeu déjà sélectionné...")
        time.sleep(self.initial_wait)

        self._focus_first_game_if_needed()

        for i in range(max_games):
            print(f"➡️ Jeu index {i}")

            self._open_selected_game()

            name_img = self._capture_region(self.game_name_region)
            time_img = self._capture_region(self.playtime_region)

            raw_name = clean_text(image_to_text(name_img))
            raw_time_text = clean_text(image_to_text(time_img))

            playtime_str = extract_playtime(raw_time_text)
            playtime_hours = playtime_to_hours(playtime_str) if playtime_str else 0.0

            if raw_name in seen_names and raw_name:
                print("⚠️ Doublon détecté, tentative de récupération...")

                self._go_back()
                time.sleep(self.back_delay)

                self._select_next_game()
                time.sleep(self.move_delay)

                self._open_selected_game()

                name_img = self._capture_region(self.game_name_region)
                time_img = self._capture_region(self.playtime_region)

                raw_name = clean_text(image_to_text(name_img))
                raw_time_text = clean_text(image_to_text(time_img))

                playtime_str = extract_playtime(raw_time_text)
                playtime_hours = playtime_to_hours(playtime_str) if playtime_str else 0.0

                if raw_name in seen_names and raw_name:
                    print("🛑 Doublon confirmé après retry, arrêt")
                    self._go_back()
                    break

            seen_names.add(raw_name)

            screenshot_path = self.screenshot_dir / f"{i:03d}_playtime.png"
            time_img.save(screenshot_path)

            results.append(
                {
                    "platform": "xbox",
                    "game_name": raw_name,
                    "playtime_raw": playtime_str,
                    "playtime_hours": playtime_hours,
                    "source": "xbox_ui_keyboard",
                }
            )

            print(f"✔ {raw_name} -> {playtime_str}")

            self._go_back()

            if i < max_games - 1:
                self._select_next_game()

        self._save(results)
        return results


if __name__ == "__main__":
    enable_dpi_awareness()

    collector = XboxUICollector(
        game_name_region=(764, 343, 529, 57),
        playtime_region=(1254, 511, 242, 31),
        open_delay=5.0,
        back_delay=4.0,
        move_delay=1.5,
        initial_wait=5.0,
        assume_first_game_already_selected=True,
    )

    collector.collect(max_games=30)